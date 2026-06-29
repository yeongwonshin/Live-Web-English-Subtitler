# Live Web English Subtitler

Live Web English Subtitler is a local desktop application that captures the system audio currently playing on a computer and displays real-time English captions in an always-on-top overlay window.

The application is designed for web video playback, but it does not depend on a specific browser, video platform, or uploaded media file. It listens to the computer's audio output, segments speech automatically, transcribes English speech with a `faster-whisper` model, and renders captions on screen.

No video or audio file upload is required.

## 1. Key Features

- Captures system playback audio instead of requiring video file uploads.
- Works independently of browser or website type, as long as the audio is routed to an available input or loopback device.
- Uses `faster-whisper` for English speech transcription.
- Displays captions in an always-on-top overlay window.
- Automatically starts transcription when speech is detected and waits during silence.
- Provides RMS audio level diagnostics with `--show-levels`.
- Supports a scrollable caption history inside the overlay.
- Allows latency and accuracy tuning through model, chunk, queue, and VAD options.
- Provides a close button and `Esc` shortcut to stop the overlay, audio capture, and transcription worker.

## 2. Platform Notes

### 2.1 Windows

Windows can usually capture system playback audio through an available loopback-style input device, depending on the audio driver and device configuration.

### 2.2 macOS

macOS does not provide system audio capture as a standard input source. A loopback device such as BlackHole is required.

When using BlackHole, browser audio must be routed to BlackHole, or to a Multi-Output Device that includes both the speakers and BlackHole.

### 2.3 Linux

Linux systems may expose system playback audio through PulseAudio or PipeWire monitor devices. The exact device name depends on the distribution and audio stack.

## 3. Installation

### 3.1 Windows

```bash
cd live_web_english_subtitler
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-windows.txt
```

### 3.2 macOS and Linux

```bash
cd live_web_english_subtitler
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-linux-mac.txt
```

## 4. macOS Audio Routing with BlackHole

### 4.1 Install BlackHole

Install BlackHole and restart macOS before checking the available audio devices.

```bash
brew install blackhole-2ch
# Restart macOS after installation.
```

After restarting, list available devices:

```bash
PYTHONPATH=$PWD/src python -m autosub --list-devices
```

`BlackHole 2ch` should appear in the device list.

### 4.2 Hear Audio While Captions Are Generated

To hear browser audio while also sending it to the subtitler, create a Multi-Output Device:

1. Open the macOS **Audio MIDI Setup** application.
2. Click the `+` button in the lower-left corner.
3. Select **Create Multi-Output Device**.
4. Enable the built-in speaker output, such as `MacBook Air Speakers`.
5. Enable `BlackHole 2ch`.
6. Open System Settings → Sound → Output.
7. Select the newly created **Multi-Output Device** as the system output.
8. Run the subtitler with the BlackHole source.

```bash
./run_mac_blackhole.sh
```

Equivalent command:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --language en --model base.en --show-levels
```

When audio is routed correctly, RMS diagnostics show a sound state:

```text
[audio] input RMS max=0.03210 threshold=0.00400 [SOUND]
```

If the browser audio is not reaching BlackHole, RMS diagnostics remain silent:

```text
[audio] input RMS max=0.00000 threshold=0.00400 [silence/too low]
```

In that case, verify that the macOS system output is set to the Multi-Output Device that includes BlackHole.

## 5. Running the Application

### 5.1 Windows

```bash
run_windows.bat
```

Equivalent command:

```bash
python -m autosub --source auto --language en --model base.en
```

### 5.2 macOS

```bash
./run_mac_blackhole.sh
```

For audio routing diagnostics:

```bash
./run_mac_blackhole_debug.sh
```

The debug launcher prints RMS sound levels so that BlackHole audio input can be verified. Caption text is still shown in the overlay window unless `--print-captions` is explicitly enabled.

### 5.3 Linux

Use the default launcher when a PulseAudio or PipeWire monitor input is available:

```bash
./run.sh
```

Or specify a monitor source explicitly:

```bash
PYTHONPATH=$PWD/src python -m autosub --source monitor --language en --model base.en --show-levels
```

## 6. Command-Line Options

Display all available options:

```bash
python -m autosub --help
```

### 6.1 List Input Devices

```bash
PYTHONPATH=$PWD/src python -m autosub --list-devices
```

### 6.2 Select a Specific Audio Source

Force the BlackHole source on macOS:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --show-levels
```

Select a source by device number:

```bash
PYTHONPATH=$PWD/src python -m autosub --source 2 --show-levels
```

Select a Linux monitor source:

```bash
PYTHONPATH=$PWD/src python -m autosub --source monitor --show-levels
```

### 6.3 Tune Speech Detection

Lower the silence threshold to detect quieter audio:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --silence-rms 0.0025 --show-levels
```

Raise the silence threshold when background noise causes false speech detection:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --silence-rms 0.012
```

### 6.4 Choose a Whisper Model

Use a faster model with lower accuracy:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model tiny.en --show-levels
```

Use a more accurate model with higher CPU cost:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model small.en --show-levels
```

Use CPU-friendly quantized inference:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model tiny.en --compute-type int8
```

## 7. Overlay Behavior

The recognized caption text is shown in the subtitle overlay window. In normal operation, captions are not printed to the terminal.

The overlay includes a small `×` close button in the top-right corner. Pressing `Esc` also closes the overlay. Closing the overlay stops audio capture and the transcription worker.

The caption window keeps a scrollable history of recognized sentence-level captions. New sentences are appended at the bottom, and earlier captions move upward. Users can scroll inside the caption window to review previous lines.

Useful overlay options:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --caption-history-size 160 --overlay-height 340
```

- `--caption-history-size`: Maximum number of sentence-level captions kept in the overlay.
- `--overlay-height`: Floating caption window height in pixels.

On macOS, the application repeatedly applies the Tkinter `topmost` attribute. If PyObjC is installed, it also applies floating window level and all-Spaces auxiliary behavior where available.

macOS may still hide separate application windows behind browser windows that use native full-screen mode. In that case, use a maximized browser window instead of the green-button full-screen mode.

## 8. Latency and Accuracy Tuning

Live transcription cannot be frame-synchronized like a pre-authored subtitle file. Audio must be captured, chunked, transcribed, and rendered before captions appear.

Shorter chunks reduce caption delay but can reduce recognition accuracy. Larger models and longer chunks can improve accuracy but increase latency.

The macOS launcher uses a low-latency profile by default. For higher accuracy with more delay:

```bash
./run_mac_blackhole.sh --model base.en --partial-chunk-seconds 1.2 --max-chunk-seconds 2.2 --transcriber-queue-size 2
```

For lower latency with potentially lower accuracy:

```bash
./run_mac_blackhole.sh --model tiny.en --partial-chunk-seconds 0.7 --max-chunk-seconds 1.2 --no-vad-filter
```

## 9. Troubleshooting

### 9.1 Captions Do Not Appear

First check whether audio is reaching the selected input device:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --show-levels --model tiny.en
```

If `[SOUND]` appears, audio input is working. Wait briefly for transcription, or use `--model tiny.en` for faster processing.

If only `[silence/too low]` appears, browser audio is not reaching the input device. On macOS, confirm that the system output is set to the Multi-Output Device that includes BlackHole.

If BlackHole does not appear in the device list, restart macOS. As an alternative, restart Core Audio and list devices again:

```bash
sudo killall coreaudiod
PYTHONPATH=$PWD/src python -m autosub --list-devices
```

### 9.2 Random Text Appears During Noise

Increase the silence threshold:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --silence-rms 0.012
```

### 9.3 CPU Transcription Is Too Slow

Use a smaller model and quantized inference:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model tiny.en --compute-type int8
```

### 9.4 Overlay Is Hidden Behind Another Window

Avoid native full-screen browser mode on macOS. Use a normal maximized browser window instead.

## 10. Project Structure

```text
live_web_english_subtitler/
├─ README.md
├─ requirements-windows.txt
├─ requirements-linux-mac.txt
├─ run_windows.bat
├─ run.sh
├─ run_mac_blackhole.sh
├─ run_mac_blackhole_debug.sh
└─ src/
   └─ autosub/
      ├─ __main__.py
      ├─ audio.py
      ├─ overlay.py
      ├─ transcriber.py
      └─ utils.py
```
