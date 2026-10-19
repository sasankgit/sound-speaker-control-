# System Audio Router

Capture audio playing through a Windows playback device and send it to
additional selected output devices. The original playback continues on the
source device. Select one or more destination devices in the control panel.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run the control panel

```powershell
python main.py
```

Choose the device Windows is currently playing through, select the additional
devices that should also play that audio, then choose **Start routing**. Use
**Stop** to end routing. Press **Refresh devices** after connecting or
disconnecting audio devices.

The app uses Windows WASAPI loopback capture, so it reads audio directly from
the selected playback endpoint. No audio file, virtual cable, or change to the
Windows default output is required.

## Command-line use

```powershell
python main.py list
python main.py route --source "{loopback-source-id}" --out 17 18
```

Use the loopback source ID and output indices shown by `list`. Destinations must
be Windows WASAPI output devices.
