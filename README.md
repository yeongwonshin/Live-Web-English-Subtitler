# Live Web English Subtitler

웹에서 영상을 재생하면, 별도 업로드 없이 **컴퓨터에서 재생 중인 시스템 오디오**를 실시간으로 캡처해 영어 자막을 화면 위에 띄우는 로컬 프로그램입니다.

- 영상 파일 업로드 없음
- 브라우저/웹사이트 종류와 무관하게 시스템 출력 오디오를 캡처
- Whisper 계열 `faster-whisper` 모델로 영어 음성 전사
- 항상 위에 표시되는 자막 오버레이 제공
- 소리가 들어오면 자동으로 전사 구간을 만들고, 무음이면 대기

> 권장 환경: Windows 10/11. Windows에서는 WASAPI loopback으로 스피커 출력을 직접 캡처합니다. macOS/Linux는 시스템 구조상 가상 오디오 장치 또는 monitor input 설정이 필요할 수 있습니다.

---

## 1. 설치

### Windows 권장 설치

PowerShell 또는 명령 프롬프트에서:

```bash
cd live_web_english_subtitler
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-windows.txt
```

### macOS / Linux 설치

```bash
cd live_web_english_subtitler
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-linux-mac.txt
```

macOS는 기본적으로 시스템 오디오 loopback을 직접 제공하지 않으므로 BlackHole, Loopback, Soundflower 같은 가상 오디오 장치가 필요할 수 있습니다. Linux는 PulseAudio/PipeWire의 `monitor` 입력 장치를 선택하면 됩니다.

---

## 2. 실행

### Windows

```bash
run_windows.bat
```

또는:

```bash
python -m autosub --source auto --language en --model base.en
```

### macOS / Linux

```bash
./run.sh
```

또는:

```bash
python -m autosub --source auto --language en --model base.en
```

실행 후 웹 브라우저에서 영어 영상을 재생하면, 소리가 감지되는 순간 자동으로 자막 생성이 시작됩니다.

---

## 3. 주요 옵션

```bash
python -m autosub --help
```

자주 쓰는 예시:

```bash
# 더 빠르게, 정확도는 낮음
python -m autosub --model tiny.en

# 정확도 조금 향상, CPU에서는 더 느림
python -m autosub --model small.en

# GPU 사용 가능 환경
python -m autosub --model small.en --device cuda --compute-type float16

# 자막 표시 시간을 길게
python -m autosub --subtitle-ttl 8

# 소리 감지 민감도 조절
python -m autosub --silence-rms 0.006
```

---

## 4. 작동 방식

1. 프로그램이 시스템 출력 오디오 또는 지정 입력 장치를 계속 감시합니다.
2. RMS 기준으로 말소리/오디오가 감지되면 버퍼링을 시작합니다.
3. 짧은 무음 또는 최대 청크 길이에 도달하면 해당 구간을 Whisper 모델에 전달합니다.
4. 인식된 영어 문장을 화면 하단 오버레이에 표시합니다.

---

## 5. 제한 사항

- 이 프로그램은 영상 파일을 분석하는 것이 아니라 **재생되는 오디오**를 듣고 자막을 생성합니다.
- DRM/브라우저/OS 오디오 정책 때문에 일부 환경에서는 시스템 오디오 캡처가 제한될 수 있습니다.
- macOS는 별도 loopback 장치 설정이 필요할 수 있습니다.
- 첫 실행 시 Whisper 모델이 다운로드되며, 이후에는 캐시됩니다.
- 실시간 전사는 컴퓨터 성능과 모델 크기에 따라 1~몇 초 지연될 수 있습니다.

---

## 6. 문제 해결

### Windows에서 소리가 안 잡힐 때

1. 영상 소리가 실제 스피커/헤드폰으로 재생되는지 확인합니다.
2. `python -m autosub --list-devices`로 장치를 확인합니다.
3. 특정 장치를 지정합니다.

```bash
python -m autosub --source "Speakers"
```

### 자막이 너무 늦게 뜰 때

```bash
python -m autosub --model tiny.en --max-chunk-seconds 3.2
```

### 잡음 때문에 아무 말이나 인식할 때

```bash
python -m autosub --silence-rms 0.015
```

### CPU가 너무 느릴 때

```bash
python -m autosub --model tiny.en --compute-type int8
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
└─ src/
   └─ autosub/
      ├─ __main__.py
      ├─ audio.py
      ├─ overlay.py
      ├─ transcriber.py
      └─ utils.py
```
