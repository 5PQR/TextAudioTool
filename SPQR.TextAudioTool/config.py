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
    import torch
    from multiprocessing import cpu_count

		
##======= SPEECH TO TEXT =======##

# The model used to process the speech into text. Larger models are better at detecting what the voice is saying, however they are considerably slower. The first time running after changing this the script will download the new whisper model if it's not already downloaded. Default is "tiny". Values: tiny, base, small, medium, large (https://github.com/openai/whisper#available-models-and-languages)
STT_MODEL = "tiny"
# The language used to detect words that are spoken. Default is "english". Other languages available and how good the model is at detecting them can be found here: https://github.com/openai/whisper#available-models-and-languages. E.g. "spanish", "japanese", etc
STT_LANGUAGE = "english"
# The time limit in seconds after which the speech recording ends even if there's still voice commands being sent. Default is 15. After 15 seconds the recording stops and the voice is processed to text.
STT_TIME_LIMIT = 15




##======= TEXT TO SPEECH  =======##
# the speech rate for the offline local voices in words per minute. Default value is 170
TTS_LOCAL_SPEECH_RATE = 170




##======= OTHER=======##

# used to print more log info
DEBUG = False




class Config:
    def __init__(self):
        self.device = "cuda:0"
        self.is_half = True
        self.n_cpu = 0
        self.gpu_name = None
        self.gpu_mem = None
        with suppress_print():
            self.x_pad, self.x_query, self.x_center, self.x_max = self.device_config()

    # has_mps is only available in nightly pytorch (for now) and MasOS 12.3+.
    # check `getattr` and try it for compatibility
    @staticmethod
    def has_mps() -> bool:
        if not torch.backends.mps.is_available():
            return False
        try:
            with suppress_print():
                torch.zeros(1).to(torch.device("mps"))
            return True
        except Exception:
            return False

    def device_config(self) -> tuple:
        if torch.cuda.is_available():
            i_device = int(self.device.split(":")[-1])
            self.gpu_name = torch.cuda.get_device_name(i_device)
            if (
                ("16" in self.gpu_name and "V100" not in self.gpu_name.upper())
                or "P40" in self.gpu_name.upper()
                or "1060" in self.gpu_name
                or "1070" in self.gpu_name
                or "1080" in self.gpu_name
            ):
                print("Found GPU", self.gpu_name, ", force to fp32")
                self.is_half = False
            else:
                print("Found GPU", self.gpu_name)
            self.gpu_mem = int(
                torch.cuda.get_device_properties(i_device).total_memory
                / 1024
                / 1024
                / 1024
                + 0.4
            )
        elif self.has_mps():
            print("No supported Nvidia GPU found, use MPS instead")
            self.device = "mps"
            self.is_half = False
        else:
            print("No supported Nvidia GPU found, use CPU instead")
            self.device = "cpu"
            self.is_half = False

        if self.n_cpu == 0:
            self.n_cpu = cpu_count()

        if self.is_half:
            # 6G????
            x_pad = 3
            x_query = 10
            x_center = 60
            x_max = 65
        else:
            # 5G????
            x_pad = 1
            x_query = 6
            x_center = 38
            x_max = 41

        if self.gpu_mem != None and self.gpu_mem <= 4:
            x_pad = 1
            x_query = 5
            x_center = 30
            x_max = 32

        return x_pad, x_query, x_center, x_max
