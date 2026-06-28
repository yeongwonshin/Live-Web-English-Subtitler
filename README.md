# Live Web English Subtitler

웹에서 영상을 재생하면, 별도 업로드 없이 **컴퓨터에서 재생 중인 시스템 오디오**를 실시간으로 캡처해 영어 자막을 화면 위에 띄우는 로컬 프로그램입니다.

- 영상 파일 업로드 없음
- 브라우저/웹사이트 종류와 무관하게 시스템 출력 오디오를 캡처
- Whisper 계열 `faster-whisper` 모델로 영어 음성 전사
- 항상 위에 표시되는 자막 오버레이 제공
- 소리가 들어오면 자동으로 전사 구간을 만들고, 무음이면 대기
- `--show-levels`로 실제 입력 오디오가 들어오는지 RMS 레벨 확인 가능

> macOS는 OS가 시스템 오디오 입력을 기본 제공하지 않으므로 BlackHole 같은 loopback 장치 설정이 필요합니다.

---

## 1. 설치

### Windows

```bash
cd live_web_english_subtitler
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-windows.txt
```

### macOS / Linux

```bash
cd live_web_english_subtitler
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-linux-mac.txt
```

---

## 2. macOS에서 웹 영상 소리 연결하기

BlackHole 설치 후에는 반드시 Mac을 재시동하세요.

```bash
brew install blackhole-2ch
# 설치 후 재시동
```

재시동 후 장치 확인:

```bash
PYTHONPATH=$PWD/src python -m autosub --list-devices
```

`BlackHole 2ch`가 보여야 합니다.

### 소리도 들으면서 자막 생성하려면

1. macOS **오디오 MIDI 설정(Audio MIDI Setup)** 앱 열기
2. 왼쪽 아래 `+` 클릭
3. **다중 출력 기기(Multi-Output Device)** 생성
4. `MacBook Air 스피커` 체크
5. `BlackHole 2ch` 체크
6. 시스템 설정 → 사운드 → 출력에서 방금 만든 **다중 출력 기기** 선택
7. 아래 명령으로 실행

```bash
./run_mac_blackhole.sh
```

또는:

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --language en --model base.en --show-levels
```

영상 재생 중 터미널에 아래처럼 나오면 오디오가 들어오는 것입니다.

```text
[audio] input RMS max=0.03210 threshold=0.00400 [SOUND]
```

계속 아래처럼 나오면 브라우저 소리가 BlackHole으로 안 들어오는 상태입니다.

```text
[audio] input RMS max=0.00000 threshold=0.00400 [silence/too low]
```

이 경우 시스템 출력이 **다중 출력 기기**인지 다시 확인하세요.

---

## 3. 실행

### Windows

```bash
run_windows.bat
```

또는:

```bash
python -m autosub --source auto --language en --model base.en
```

### macOS

```bash
./run_mac_blackhole.sh
```

### Linux

PulseAudio/PipeWire monitor 입력이 있으면:

```bash
./run.sh
```

또는 장치 이름을 지정합니다.

```bash
PYTHONPATH=$PWD/src python -m autosub --source monitor --language en --model base.en --show-levels
```

---

## 4. 주요 옵션

```bash
python -m autosub --help
```

자주 쓰는 예시:

```bash
# 입력 장치 목록 확인
PYTHONPATH=$PWD/src python -m autosub --list-devices

# macOS BlackHole 강제 선택
PYTHONPATH=$PWD/src python -m autosub --source blackhole --show-levels

# 장치 번호로 직접 선택
PYTHONPATH=$PWD/src python -m autosub --source 2 --show-levels

# 소리 감지 민감도 올리기: 작은 소리도 감지
PYTHONPATH=$PWD/src python -m autosub --source blackhole --silence-rms 0.0025 --show-levels

# 더 빠르게, 정확도는 낮음
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model tiny.en --show-levels

# 정확도 조금 향상, CPU에서는 더 느림
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model small.en --show-levels
```

---

## 5. 자막창이 다른 창 뒤로 숨길 때

이번 버전은 Tkinter `topmost`를 반복 적용하고, macOS에서는 PyObjC가 설치되어 있으면 floating window level과 all-Spaces 보조 속성을 적용합니다.

그래도 macOS의 브라우저 **진짜 전체화면 모드**에서는 OS 정책상 별도 앱 창이 가려질 수 있습니다. 그 경우 브라우저를 초록 버튼 전체화면 대신 일반 창 최대화 상태로 사용하세요.

---

## 6. 문제 해결

### 영상 틀어도 자막이 안 나올 때

먼저 RMS 레벨을 확인하세요.

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --show-levels --model tiny.en
```

- `[SOUND]`가 뜨면 오디오는 들어오고 있습니다. 조금 기다리거나 `--model tiny.en`으로 속도를 높여 보세요.
- `[silence/too low]`만 뜨면 브라우저 소리가 BlackHole으로 안 들어오고 있습니다. macOS 출력 장치를 **다중 출력 기기**로 바꾸세요.
- `BlackHole` 장치가 목록에 없으면 재시동하거나 `sudo killall coreaudiod` 후 다시 확인하세요.

### 잡음 때문에 아무 말이나 인식할 때

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --silence-rms 0.012
```

### CPU가 너무 느릴 때

```bash
PYTHONPATH=$PWD/src python -m autosub --source blackhole --model tiny.en --compute-type int8
```

---

## 7. 파일 구조

```text
live_web_english_subtitler/
├─ README.md
├─ requirements-windows.txt
├─ requirements-linux-mac.txt
├─ run_windows.bat
├─ run.sh
├─ run_mac_blackhole.sh
└─ src/
   └─ autosub/
      ├─ __main__.py
      ├─ audio.py
      ├─ overlay.py
      ├─ transcriber.py
      └─ utils.py
```


## v3 notes: overlay-only captions and close button

Normal run command:

```bash
./run_mac_blackhole.sh
```

In normal mode, recognized subtitle text is shown only in the subtitle overlay window. It is not printed in the terminal.

The overlay now has a small `×` close button in the top-right corner. You can also press `Esc` to close it. Closing the overlay stops the audio capture and transcription worker.

For troubleshooting audio routing only, use:

```bash
./run_mac_blackhole_debug.sh
```

Debug mode prints RMS sound levels so you can confirm that BlackHole is receiving audio. It still does not print subtitle text unless you explicitly add `--print-captions`.

## Sync / latency tuning

The macOS launcher now defaults to a low-latency profile: `tiny.en`, beam size 1, short rolling chunks, and a queue size of 1. This reduces the delay between browser audio and the overlay caption.

For better accuracy at the cost of more delay, run:

```bash
./run_mac_blackhole.sh --model base.en --partial-chunk-seconds 1.2 --max-chunk-seconds 2.2 --transcriber-queue-size 2
```

For the lowest latency, run:

```bash
./run_mac_blackhole.sh --model tiny.en --partial-chunk-seconds 0.7 --max-chunk-seconds 1.2 --no-vad-filter
```

Live transcription cannot be perfectly frame-synced like a subtitle file because the audio must be captured, chunked, transcribed, and then rendered. Shorter chunks reduce delay but can lower recognition accuracy.

