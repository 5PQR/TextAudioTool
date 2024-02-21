import config
import os
import http.server
import socketserver
import json
import importlib
import subprocess
from urllib.parse import unquote


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
