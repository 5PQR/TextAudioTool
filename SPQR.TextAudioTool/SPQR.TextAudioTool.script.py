import config
import os
import contextlib
import warnings
warnings.filterwarnings('ignore')

#
# Python spam suppression...
#
@contextlib.contextmanager
def suppress_print():
	with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
		yield

with suppress_print():
    import http.server
    import socketserver
    import json
    import importlib
    import subprocess
    from urllib.parse import unquote


#
# RVC
#

with suppress_print():
	import time
	from pathlib import Path
	import random
	import sys
	import traceback
	import librosa
	import html
	import torch
	import asyncio
	from scipy.io import wavfile
	import numpy as np
	from threading import Thread
	from fairseq import checkpoint_utils

	import tts_preprocessor
	from my_utils import load_audio
	from rmvpe import RMVPE
	from vc_infer_pipeline import VC
	from lib.infer_pack.models import (
		SynthesizerTrnMs256NSFsid,
		SynthesizerTrnMs256NSFsid_nono,
		SynthesizerTrnMs768NSFsid,
		SynthesizerTrnMs768NSFsid_nono,
	)
	from config import Config

	torch._C._jit_set_profiling_mode(False)

rvc_params = {
	'rvc_model': '',    # the folder name containing the model inside rvc_models/ (index loaded also if it's there)'
	'transpose': 0,     # pitch adjust up+/down-
	'index_rate': 1,    # strength of accent to use from the RVC model
	'protect': 0.33     # protect non-words, probably not important for SAPI.
}
current_params = rvc_params.copy()

with suppress_print():
    rvc_config = Config()
    
hubert_model = None
rmvpe_model = None

with suppress_print():
	def load_hubert():
		global hubert_model
		models, _, _ = checkpoint_utils.load_model_ensemble_and_task(
			["models/hubert_base.pt"],
			suffix="",
		)
		hubert_model = models[0]
		hubert_model = hubert_model.to(rvc_config.device)
		if rvc_config.is_half:
			hubert_model = hubert_model.half()
		else:
			hubert_model = hubert_model.float()
			
		return hubert_model.eval()
	
def get_all_paths(relative_directory, filetype=None):
	folders = []
	files = []

	for dirpath, dirnames, filenames in os.walk(relative_directory):
		for dirname in dirnames:
			folders.append(os.path.relpath(os.path.join(dirpath, dirname), relative_directory))
		for filename in filenames:
			if filetype is None or filename.endswith(filetype):
				files.append(os.path.relpath(os.path.join(dirpath, filename), relative_directory))

	return folders, files
	
# RVC functions, retrieved via https://github.com/litagin02/rvc-tts-webui

# used to only load new model, if it actually changes...
previous_model = None
cpt = None

def model_data(model_name):
	# global n_spk, tgt_sr, net_g, vc, cpt, version, index_file
	global previous_model, cpt
	
	pth_path = ''
	index_path = ''
	
	for file in os.listdir(f'rvc_models/{model_name}/'):
		ext = os.path.splitext(file)[1]
		if ext == '.pth':
			pth_path = f'rvc_models/{model_name}/{file}'
			#print(f"Model Found: {pth_path}")
		if ext == '.index':
			index_path = f'rvc_models/{model_name}/{file}'
			#print(f"Index Found: {index_path}")
	
	if pth_path != previous_model:
		cpt = torch.load(pth_path, map_location="cpu")
	
	if "config" not in cpt or "weight" not in cpt:
		raise ValueError(f'Incorrect format for {pth_path}. Use a voice model trained using RVC v2 instead.')
		
	tgt_sr = cpt["config"][-1]
	cpt["config"][-3] = cpt["weight"]["emb_g.weight"].shape[0]	# n_spk
	if_f0 = cpt.get("f0", 1)
	version = cpt.get("version", "v1")
	if version == "v1":
		if if_f0 == 1:
			net_g = SynthesizerTrnMs256NSFsid(*cpt["config"], is_half=rvc_config.is_half)
		else:
			net_g = SynthesizerTrnMs256NSFsid_nono(*cpt["config"])
	elif version == "v2":
		if if_f0 == 1:
			net_g = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=rvc_config.is_half)
		else:
			net_g = SynthesizerTrnMs768NSFsid_nono(*cpt["config"])
	else:
		raise ValueError("Unknown RVC model version")
	del net_g.enc_q
	net_g.load_state_dict(cpt["weight"], strict=False)
	net_g.eval().to('cuda')
	
	#net_g = net_g.half()
	if rvc_config.is_half:
		net_g = net_g.half()
	else:
		net_g = net_g.float()
	
	with suppress_print():
		vc = VC(tgt_sr, rvc_config)
		
	# n_spk = cpt["config"][-3]

	if pth_path != previous_model:
		#print(f"Model {model_name} loaded.")
		if index_path != '':
			print(f'Model rvc_models/{model_name}/{file} loaded.')
			print(f'Index rvc_models/{index_path}/{file} will be used.')
		else:
			print(f'Model rvc_models/{model_name}/{file} loaded.')
			
	previous_model = pth_path

	return tgt_sr, net_g, vc, version, index_path, if_f0


def rvc(
	output_file,
	model_name,
	f0_up_key=1,
	f0_method='rmvpe',
	index_rate=1,
	protect=0.33,
	filter_radius=3,
	resample_sr=0,
	rms_mix_rate=0.25,
):
	try:
		global hubert_model, rmvpe_model

		edge_output_filename = output_file

		with suppress_print():
			tgt_sr, net_g, vc, version, index_file, if_f0 = model_data(model_name)
		
		with suppress_print():
			audio, sr = librosa.load(edge_output_filename, sr=16000, mono=True)
			#audio, sr = librosa.load(edge_output_filename, mono=True)
			#audio = load_audio(edge_output_filename, 16000)
		
		#duration = len(audio) / sr
		#print(f"IsHalf: {rvc_config.is_half}")
		#print(f"Audio duration: {duration}s")
	
		f0_up_key = int(f0_up_key)

		if not hubert_model:
			load_hubert()
		if f0_method == "rmvpe":
			vc.model_rmvpe = rmvpe_model
		times = [0, 0, 0]
		
		with suppress_print():
			audio_opt = vc.pipeline(
				hubert_model,
				net_g,
				0,
				audio,
				edge_output_filename,
				times,
				f0_up_key,
				f0_method,
				index_file,
				# file_big_npy,
				index_rate,
				if_f0,
				filter_radius,
				tgt_sr,
				resample_sr,
				rms_mix_rate,
				version,
				protect,
				None,
			)
		if tgt_sr != resample_sr and resample_sr >= 16000:
			tgt_sr = resample_sr
			print("resample_sr")
		info = f"Success."
		#print(info)
		#print("Success.")
		return audio_opt
	
	except:
		info = traceback.format_exc()
		print(info)
		return info, None, None

print("Loading hubert model...")
with suppress_print():
	hubert_model = load_hubert()
#print("Hubert model loaded.")

print("Loading rmvpe model...")
with suppress_print():
	rmvpe_model = RMVPE("models/rmvpe.pt", rvc_config.is_half, rvc_config.device)
#print("rmvpe model loaded.")

#
# END - RVC
#

print("------------------------------------------------------------------------------")
print("                                                                              ")
print("                 .M\"\"\"bgd `7MM\"\"\"Mq.   .g8\"\"8q. `7MM\"\"\"Mq.         ")
print("                ,MI    \"Y   MM   `MM..dP'    `YM. MM   `MM.                  ")
print("                `MMb.       MM   ,M9 dM'      `MM MM   ,M9                    ")
print("                  `YMMNq.   MMmmdM9  MM        MM MMmmdM9                     ")
print("                .     `MM   MM       MM.      ,MP MM  YM.                     ")
print("                Mb     dM   MM       `Mb.    ,dP' MM   `Mb.                   ")
print("                P\"Ybmmd\"  .JMML.       `\"bmmd\"' .JMML. .JMM.              ")
print("                                           MMb                                ")
print("                                            `Ybm9'                            ")
print("==============================================================================")


print("  _____ _______  _______      _   _   _ ____ ___ ___    _____ ___   ___  _     ")
print(" |_   _| ____\ \/ /_   _|    / \ | | | |  _ \_ _/ _ \  |_   _/ _ \ / _ \| |    ")
print("   | | |  _|  \  /  | |     / _ \| | | | | | | | | | |   | || | | | | | | |    ")
print("   | | | |___ /  \  | |    / ___ \ |_| | |_| | | |_| |   | || |_| | |_| | |___ ")
print("   |_| |_____/_/\_\ |_|   /_/   \_\___/|____/___\___/    |_| \___/ \___/|_____|")
print("                                                                               ")


print("------------------------------------------------------------------------------")
print("    AVAILABLE ENDPOINTS:")
print("    127.0.0.1:7069/speak POST - reads text to audio file")
print("    127.0.0.1:7069/read GET                     - reads files/tts_read.wav ") 
print("    127.0.0.1:7069/status GET                   - returns the status of the tool")
print("    127.0.0.1:7069/voices GET                   - returns list of available voices")
print("    127.0.0.1:7069/listen-whisper GET           - listens and returns speech to text")
print("    127.0.0.1:7069/speakelevenlabs POST - reads text to audio file with elevenlabs")
print("    127.0.0.1:7069/userelevenlabs GET - gets elevenlabs user available tokens count")
print("    127.0.0.1:7069/modelselevenlabs GET - gets elevenlabs available AI models")
print("    127.0.0.1:7069/voiceselevenlabs GET - gets elevenlabs available voices")
print("    More details and endpoint tests in demo/demo.html")
print("------------------------------------------------------------------------------")
print("    Help me make more cool stuff at: patreon.com/spqr_aeternum")
print("==============================================================================")



RECORD_FILE_PATH = "files/tts_read.wav"
ELEVENLABS_API = "https://api.elevenlabs.io/"
SCRIPT_OK = True

class SPQRTTSHandler(http.server.BaseHTTPRequestHandler):
	def end_headers(self): 
		self.send_header('Access-Control-Allow-Origin', '*')
		super().end_headers()
	def do_POST(self):
		if self.path == '/speak':
			content_length = int(self.headers['Content-Length'])
			post_data = self.rfile.read(content_length)
			data = json.loads(post_data.decode('utf-8'))
			text = data['message']
			print("Received text to speak ...")
			selected_voice = ""
			default_voice = ""
			
			engine = pyttsx3.init()
			voices = engine.getProperty('voices')
			for voice in voices:
				if default_voice == "":
					default_voice = voice.id
				if voice.name == data['voice']:
					selected_voice = voice.id
			if selected_voice == "":
				selected_voice = default_voice
				
			# Set the voice to use (optional)
			engine.setProperty('voice', selected_voice)
			engine.setProperty('rate',config.TTS_LOCAL_SPEECH_RATE)
			#Save text
			output_path = "spqr_tts_latest.wav";
			if data['output'] != "":
				output_path  = data['output']
			engine.save_to_file(text , output_path)
			engine.runAndWait()
			
			#
			# RVC
			#
			if data['rvc_voice'] != None:
				# RVC Voice Specified - The switching is handled by RVC code above as required...
				rvc_params['rvc_model'] = data['rvc_voice']
			else:
				rvc_params['rvc_model'] = ""
				
			if data['rvc_pitch'] != None:
				rvc_params['transpose'] = data['rvc_pitch']
			else:
				rvc_params['transpose'] = 0
				
			if rvc_params['rvc_model'] != None and rvc_params['rvc_model'] != "":
				#print('Running RVC')
				audio = rvc(output_path, rvc_params['rvc_model'], rvc_params['transpose'], 'rmvpe', rvc_params['index_rate'], rvc_params['protect'])
				wavfile.write(output_path, 44100, audio.astype(np.int16))
			#
			# END - RVC
			#

			# Send a response
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": "done",
				"saved": output_path
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
		elif self.path.startswith('/speakelevenlabs'):
			content_length = int(self.headers['Content-Length'])
			post_data = self.rfile.read(content_length)
			data = json.loads(post_data.decode('utf-8'))
			query_params = getParams(self.path)
			print("Received text to speak ...")
			
			headers = {'xi-api-key': self.headers['xi-api-key']}
			url = ELEVENLABS_API + "v1/text-to-speech/"+query_params["voice"]+"?optimize_streaming_latency="+query_params["optimize_streaming_latency"];
			try:
				response = requests.post(url, headers=headers,json=data)
				response_bytes = response.content
			except requests.exceptions.RequestException as e:
				print("Error making ELEVENLABS_API POST request:", e)
		   
			
		   
			#Save text
			output_path = "spqr_tts_latest_elevenlabs.mp3";
			if query_params['output'] != "":
				output_path  = query_params['output']
				
			absolute_path = os.path.abspath(output_path)
			with open(absolute_path, 'wb') as f:
				f.write(response_bytes)

			# Send a response
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": "done",
				"saved": output_path
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
	def do_GET(self):
		if self.path == '/voices':
			engine = pyttsx3.init()
			voices = engine.getProperty('voices')
			print("Available voices:")           
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
			}
			for voice in voices:
			   response[voice.id.split("\\")[-1]] = voice.name
			self.wfile.write(json.dumps(response).encode('utf-8'))
		elif self.path == '/voiceselevenlabs':
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
						
			headers = {'xi-api-key': self.headers['xi-api-key']}
			url = ELEVENLABS_API + "v1/voices";
			try:
				response = requests.get(url, headers=headers)
				response_string = response.text
				response_bytes = response_string.encode('utf-8')
			except requests.exceptions.RequestException as e:
				print("Error making ELEVENLABS_API GET request:", e)
			self.wfile.write(response_bytes)
		elif self.path == '/modelselevenlabs':
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
						
			headers = {'xi-api-key': self.headers['xi-api-key']}
			url = ELEVENLABS_API + "v1/models";
			try:
				response = requests.get(url, headers=headers)
				response_string = response.text
				response_bytes = response_string.encode('utf-8')
			except requests.exceptions.RequestException as e:
				print("Error making ELEVENLABS_API GET request:", e)
			self.wfile.write(response_bytes)
		elif self.path == '/userelevenlabs':
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
						
			headers = {'xi-api-key': self.headers['xi-api-key']}
			url = ELEVENLABS_API + "v1/user";
			try:
				response = requests.get(url, headers=headers)
				response_string = response.text
				response_bytes = response_string.encode('utf-8')
			except requests.exceptions.RequestException as e:
				print("Error making ELEVENLABS_API GET request:", e)
			self.wfile.write(response_bytes)
		elif self.path == '/listen':
			read_text = ""
			read_text_error = ""
			read_text_status = "error"
			
			try:
				r = sr.Recognizer()
				with sr.Microphone() as source:                # use the default microphone as the audio source
					audio = r.adjust_for_ambient_noise(source) # listen for 1 second to calibrate the energy threshold for ambient noise levels
					audio = r.listen(source, timeout=5, phrase_time_limit=15)  # now when we listen, the energy threshold is already set to a good value
				read_text_sphinx = r.recognize_sphinx(audio)
				read_text = read_text_sphinx
				read_text_status = "ok"
			except LookupError:                            # speech is unintelligible
				read_text_error = "Could not understand audio"
			except sr.WaitTimeoutError as e:                       
				read_text_error = "Timed out waiting for audio"
		
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": read_text_status,
				"text": read_text,
				"error": read_text_error
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
		elif self.path == '/listen-whisper':
			read_text = ""
			read_text_error = ""
			read_text_status = "error"
			
			try:
				r = sr.Recognizer()
				with sr.Microphone() as source:                # use the default microphone as the audio source
					audio = r.adjust_for_ambient_noise(source) # listen for 1 second to calibrate the energy threshold for ambient noise levels
					audio = r.listen(source, timeout=4, phrase_time_limit=config.STT_TIME_LIMIT)  # now when we listen, the energy threshold is already set to a good value
				read_text_whisper = r.recognize_whisper(audio_data=audio, model=config.STT_MODEL, language=config.STT_LANGUAGE)
				read_text = read_text_whisper
				read_text_status = "ok"
			except Exception as e:
				read_text_error = f"An error occurred: {str(e)}"
		
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": read_text_status,
				"text": read_text,
				"error": read_text_error
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
		elif self.path == '/read':
			read_text = ""
			read_text_error = ""
			read_text_status = "error"
			
			r = sr.Recognizer()
			with sr.AudioFile(RECORD_FILE_PATH) as source:
				audio = r.record(source)  # read the entire audio file

			# recognize speech using Sphinx
			try:
				read_text_sphinx = r.recognize_sphinx(audio)
				read_text = read_text_sphinx
				read_text_status = "ok"
			except sr.UnknownValueError:
				read_text_error = "Sphinx could not understand audio"
			except sr.RequestError as e:
				read_text_error = "Sphinx error; {0}".format(e)
		
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": read_text_status,
				"text": read_text,
				"error": read_text_error
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
		elif self.path == '/status':
			self.send_response(200)
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			response = {
				"status": "running"
			}
			self.wfile.write(json.dumps(response).encode('utf-8'))
		else:
			self.send_response(404)
			self.end_headers()

def getParams(url):
	query_params = {}
	if '?' in url:
		query_string = url.split('?')[1]
		query_params_list = query_string.split('&')
		for param in query_params_list:
			key_value = param.split('=')
			if len(key_value) == 2:
				key_value[0] = unquote(key_value[0])
				key_value[1] = unquote(key_value[1])
				query_params[key_value[0]] = key_value[1]
	return query_params

def check_and_install_package(package_name):
	global SCRIPT_OK
	if not SCRIPT_OK:
		return
	try:
		importlib.import_module(package_name)
		print(f"    {package_name} is already installed.")
	except ImportError:
		print(f"    {package_name} Checking...")
		if config.DEBUG:
			subprocess.call(['pip', 'install', package_name])
		else:
			subprocess.call(['pip', 'install', package_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		print(f"    Package ok: {package_name}!")
		
def check_ffmpeg_installed():
	global SCRIPT_OK
	print("Checking ffmpeg ...")
	try:
		subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
		print("    ffmpeg is installed. Proceeding with the script...")
	except Exception as e:
		print("    Error: ffmpeg is not installed.")
		print("    Please install ffmpeg and try again. If it's installed but it doesn't work, it needs to be added to the system environment variables.")
		SCRIPT_OK = False

#check if ffmpeg is installed
if SCRIPT_OK:
	check_ffmpeg_installed()
		
# Check and install packages
check_and_install_package('pyttsx3')
check_and_install_package('SpeechRecognition')
check_and_install_package('pocketsphinx')
check_and_install_package('PyAudio')
check_and_install_package('pysoundfile')
check_and_install_package('openai-whisper')
check_and_install_package('pywintypes')
#
# RVC
#
check_and_install_package('contextlib')
check_and_install_package('librosa')
#check_and_install_package('librosa')
#check_and_install_package('librosa')
#check_and_install_package('librosa')
#check_and_install_package('librosa')
#check_and_install_package('librosa')
#
# END - RVC
#


if SCRIPT_OK:
	import pyttsx3
	import requests
	import soundfile
	import speech_recognition as sr
	import warnings
	warnings.filterwarnings("ignore", message=".*The 'nopython' keyword.*")
	import whisper
	print("    Checking for Whisper model...")
	model = whisper.load_model(config.STT_MODEL)

	httpd = socketserver.TCPServer(('127.0.0.1', 7069), SPQRTTSHandler)
	print("==============================================================================")
	print("              ██████  ███████  █████  ██████  ██    ██ ██ ")
	print("              ██   ██ ██      ██   ██ ██   ██  ██  ██  ██ ")
	print("              ██████  █████   ███████ ██   ██   ████   ██ ")
	print("              ██   ██ ██      ██   ██ ██   ██    ██       ")
	print("              ██   ██ ███████ ██   ██ ██████     ██    ██ ")
	print("------------------------------------------------------------------------------")
	print("    Listening for incoming requests...")
	httpd.serve_forever()
