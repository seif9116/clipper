import os
import shutil
import threading
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import time
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import imageio_ffmpeg

# Set ffmpeg path for pydub/ffmpeg-python
# This is crucial for environments where ffmpeg is not globally installed
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())

from clipper_engine.pipeline import ClipperPipeline
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "clipper_output/uploads"
OUTPUT_DIR = "clipper_output"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Simple job store with persistence
JOBS_FILE = os.path.join(OUTPUT_DIR, "jobs.json")
jobs: Dict[str, Dict] = {}

def load_jobs():
    global jobs
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r") as f:
                jobs = json.load(f)
        except Exception as e:
            print(f"Failed to load jobs: {e}")
            jobs = {}

def save_jobs():
    try:
        with open(JOBS_FILE, "w") as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Failed to save jobs: {e}")

# Initial load
load_jobs()

class JobStatus(BaseModel):
    id: str
    status: str
    clips: List[str] = []

def run_pipeline_task(job_id: str, file_path: str, api_key: str, openai_key: str):
    jobs[job_id]["status"] = "processing"
    save_jobs()
    
    def update_progress(stage):
        jobs[job_id]["status"] = stage
        save_jobs()

    try:
        # Create deterministic run directory based on file path
        # This allows us to find clips later for the same file
        run_dir = file_path + "_data"
        
        # Pass both keys to pipeline
        pipeline = ClipperPipeline(output_base_dir=OUTPUT_DIR, api_key=api_key, openai_key=openai_key)
        clips = pipeline.run(file_path, progress_callback=update_progress, specific_run_dir=run_dir)
        
        # Store clips with metadata
        clips_json_path = os.path.join(run_dir, "clips.json")
        full_clips_data = []
        
        if os.path.exists(clips_json_path):
            with open(clips_json_path, "r") as f:
                full_clips_data = json.load(f)
                
            # Add relative path to each clip
            for clip in full_clips_data:
                if "filename" in clip:
                    # Construct where it should be
                    clip_path = os.path.join(run_dir, "clips", clip["filename"])
                    clip["path"] = os.path.relpath(clip_path, OUTPUT_DIR)
        else:
            # Fallback if no json (shouldn't happen with new pipeline)
            rel_clips = [os.path.relpath(p, OUTPUT_DIR) for p in clips]
            full_clips_data = [{"path": p} for p in rel_clips]
        
        jobs[job_id]["clips"] = full_clips_data
        jobs[job_id]["status"] = "done"
        save_jobs()
    except Exception as e:
        print(f"Job failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        save_jobs()

@app.post("/api/upload")
def upload_video(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "path": file_path}

@app.post("/api/process")
async def process_video(background_tasks: BackgroundTasks, path: str, gemini_api_key: str, openai_api_key: str):
    api_key = gemini_api_key
    openai_key = openai_api_key
    
    if not api_key:
        # Fallback for local dev if they have it in .env, though frontend should send it
        api_key = os.getenv("GEMINI_API_KEY")

    if not openai_key:
        openai_key = os.getenv("OPENAI_API_KEY")
        
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required")
    
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API Key is required")

    job_id = f"job_{int(time.time())}"
    jobs[job_id] = {"id": job_id, "status": "queued", "clips": []}
    save_jobs()
    
    background_tasks.add_task(run_pipeline_task, job_id, path, api_key, openai_key)
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/uploads")
def get_uploads():
    files = []
    if not os.path.exists(UPLOAD_DIR):
        return []
        
    for filename in os.listdir(UPLOAD_DIR):
        if filename.endswith(".transcript.txt") or filename.endswith(".jpg"):
            continue
            
        # Is it a media file?
        low_f = filename.lower()
        if low_f.endswith(('.mp4', '.mkv', '.avi', '.mov', '.mp3', '.wav')):
            file_path = os.path.join(UPLOAD_DIR, filename)
            transcript_path = file_path + ".transcript.txt"
            
            # Generate thumbnail if video and missing
            thumb_filename = filename + ".jpg"
            thumb_path = os.path.join(UPLOAD_DIR, thumb_filename)
            
            # Only try generating for video types, and if not exists
            if not os.path.exists(thumb_path) and not low_f.endswith(('.mp3', '.wav')):
                try:
                    import ffmpeg
                    # Extract frame at 1s, scale to 320 width
                    (
                        ffmpeg
                        .input(file_path, ss=1)
                        .filter('scale', 320, -1)
                        .output(thumb_path, vframes=1)
                        .overwrite_output()
                        .run(quiet=True, cmd=imageio_ffmpeg.get_ffmpeg_exe())
                    )
                except Exception as e:
                    print(f"Failed to generate thumb for {filename}: {e}")

            has_thumb = os.path.exists(thumb_path)
            
            # Check for existing clips
            run_dir = file_path + "_data"
            clips_dir = os.path.join(run_dir, "clips")
            clips_json_path = os.path.join(run_dir, "clips.json")
            existing_clips = []
            
            if os.path.exists(clips_json_path):
                try:
                    with open(clips_json_path, "r") as f:
                        meta_clips = json.load(f)
                        
                    for clip in meta_clips:
                        if "filename" in clip:
                            full_p = os.path.join(clips_dir, clip["filename"])
                            if os.path.exists(full_p):
                                clip["path"] = os.path.relpath(full_p, OUTPUT_DIR)
                                existing_clips.append(clip)
                except Exception as e:
                    print(f"Error loading clips.json for {filename}: {e}")
                    
            # Fallback: if json failed or didn't exist, but dir has files
            if not existing_clips and os.path.exists(clips_dir):
                for c in sorted(os.listdir(clips_dir)):
                    if c.endswith(".mp4"):
                        full_p = os.path.join(clips_dir, c)
                        rel = os.path.relpath(full_p, OUTPUT_DIR)
                        existing_clips.append({"path": rel, "title": "Clip", "transcript_text": ""})

            files.append({
                "filename": filename,
                "path": file_path,
                "thumbnail": f"uploads/{thumb_filename}" if has_thumb else None,
                "has_transcript": os.path.exists(transcript_path),
                "clips": existing_clips,
                "created_at": os.path.getctime(file_path)
            })
    
    # Sort by newest first
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files

# Serve output files (including clips)
app.mount("/static", StaticFiles(directory=OUTPUT_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
