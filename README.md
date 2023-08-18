# About TextAudioTool
Very quick & simple python tool that creates local api endpoints for TTS &amp; STT. It was created for a Virt-A-Mate mod but it can be used for other games & applications too.
It installs miniconda and the required dependencies, then starts a local server running at 127.0.0.1:7069 which has endpoints for local TTS (old school SAPI voices) and STT (using Whisper - tiny version).

![img](https://github.com/5PQR/TextAudioTool/assets/122448634/7aeb85c7-0b09-4cb6-a177-172911639139)


# Install for VaM
## 1. Install ffmpeg
ffmpeg is a tool that converts videos & audio files. Whisper needs it to do it's STT magic (https://github.com/openai/whisper#setup)
if you don't already have it you can install it by following this guide https://www.wikihow.com/Install-FFmpeg-on-Windows. **There are basically two big steps**: 1) download ffmpeg, then 2) add ffmpeg to the system environment variables. You can check if you have it by opening command prompt and typing "ffmpeg".

![img2](https://github.com/5PQR/TextAudioTool/assets/122448634/331d678f-db29-49e5-9048-d2ccf5eadd56)

Tip: after you install it, if you want to check if it works, type it in a new command prompt window. If it's an old window from before the install, it will still show as not found. 

## 2. Download files
You can get the zip from https://github.com/5PQR/TextAudioTool/releases/latest and extract the file in the VaM folder, so that the .bat files like "SPQR.TextAudioTool - (VaM.exe).bat" & the SPQR.TextAudioTool folder are in the same folder as VaM.exe.

![img3](https://github.com/5PQR/TextAudioTool/assets/122448634/d9646779-7ba9-474d-882a-0cc3b19ce091)


## 3. Install 
You can now run **SPQR.TextAudioTool - (standalone).bat** and it will automatically install in SPQR.TextAudioTool/installer_files the dependencies it needs. The first time it will take a couple of minutes, but after that it should be quicker. The other bat files do the same thing, but also open VaM. I added them to have a single shortcut open VaM and the text audio tool at the same time.

If everything went OK, the command prompt should show READY and the tool's endpoints should be available:
![img4](https://github.com/5PQR/TextAudioTool/assets/122448634/2bcfc915-bb97-440d-b72f-76455d6b20b7)


## 4.Run
After installing it's best to close it and opening the tool again. You can test the endpoints in a browser by opening demo/demo.html. Hitting "Test response" buttons should generate responses similar to the example ones if everything is working properly.

# Config
You can edit SPQR.TextAudioTool\config.py in any text editor and change there a few settings like the WPM rate for the offline voice and the language and model type used for detecting speech to text. More info about each setting can be found in the file.

# Usage for VaM
When the tool is running, it should be possible from VaM to do TTS & STT by accessing the endpoints.
The tool can be opened/closed at any time. I added the extra bat files like "SPQR.TextAudioTool - VaM (Desktop Mode).bat" as a shortcut to open both vam + the text audio tool, but the tool can be opened later too from "SPQR.TextAudioTool - (standalone).bat" even after VaM is already running.

# Usage for other applications
Same as above but only the **SPQR.TextAudioTool** folder is necessary, the extra .bat files can be removed, or you can keep just the bat with (standalone) in the name. To run it you can open SPQR.TextAudioTool.bat directly, or the (standalone) bat which is a shortcut to the one inside the folder, meant to be easier to find.

# Credits
* The installer script is based on oobabooga's install script made for https://github.com/oobabooga/one-click-installers
