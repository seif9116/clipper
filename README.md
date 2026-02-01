# AI Video Clipper

A project to automatically repurpose long-form videos into viral short clips (vertical 9:16).

## Usage

### 1. Setup
Install dependencies using [uv](https://github.com/astral-sh/uv):
```bash
uv pip install -r requirements.txt
```

Set up API Key in `.env`:
```env
GEMINI_API_KEY=your_key_here
```

### Manual Setup (without uv)
If you prefer not to use `uv`, you can use standard pip and venv:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Command Line Interface
Run directly on a video:
```bash
uv run python clipper_engine/main_cli.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

Or with manual venv:
```bash
source .venv/bin/activate
python clipper_engine/main_cli.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

### 3. Web Interface
**Quick Start:**
Run the following script to start both the backend and frontend:
```bash
./start.sh
```

**Manual Start:**

**Backend:**
Run from the project root:
```bash
uv run uvicorn backend.main:app --reload
```

**Frontend:**
In a new terminal:
```bash
cd frontend
npm install # if not done
npm run dev
```
Open `http://localhost:5173` in your browser.

## Architecture

-   **Downloader**: `yt-dlp` to get video/audio.
-   **Transcriber**: `faster-whisper` for speech-to-text.
-   **Analyzer**: Google Gemini (via `google-genai`) to find viral segments.
-   **Cropper**: `mediapipe` to detect faces and center the crop.
-   **Compositor**: `ffmpeg` to render the final clip.
-   **Backend**: FastAPI.
-   **Frontend**: React + Vite + TailwindCSS.
