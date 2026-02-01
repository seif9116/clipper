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
# CORS
origins = [
    "http://localhost:5173",  # Local Vite frontend
    "http://localhost:3000",  # Local alternative
    "https://seifeldin.ca",
    "https://www.seifeldin.ca",
    "https://clipper-weld-ten.vercel.app", # Vercel deployment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    import uuid
    # Use UUID for filename to prevent guessing and collisions
    ext = os.path.splitext(file.filename)[1]
    if not ext:
        ext = ".mp4"
    
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": unique_name, "path": file_path, "original_name": file.filename}

@app.post("/api/process")
async def process_video(background_tasks: BackgroundTasks, path: str, gemini_api_key: str, openai_api_key: str):
    api_key = gemini_api_key
    openai_key = openai_api_key
    
    if not api_key:
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
    
    # Trigger cleanup task
    background_tasks.add_task(cleanup_old_files)
    
    return {"job_id": job_id}

def cleanup_old_files():
    """Deletes files older than 1 hour."""
    try:
        now = time.time()
        # 1 hour retention
        retention = 3600 
        
        # Cleanup UPLOAD_DIR
        for f in os.listdir(UPLOAD_DIR):
            f_path = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(f_path):
                if os.stat(f_path).st_mtime < now - retention:
                    print(f"Deleting old file: {f}")
                    os.remove(f_path)
                    
        # Cleanup OUTPUT_DIR (jobs.json, run folders)
        # Note: jobs.json needs to be handled carefully, maybe don't delete it or it wipes job history for everyone?
        # For strict privacy we should probably wipe it or not use a single file. 
        # But for now let's just clean up job directories.
        
        for f in os.listdir(OUTPUT_DIR):
            f_path = os.path.join(OUTPUT_DIR, f)
            if os.path.isdir(f_path) and f.startswith("run_"):
                 if os.path.getmtime(f_path) < now - retention:
                     print(f"Deleting old run: {f}")
                     shutil.rmtree(f_path)
                     
            # Also clean up generated clip folders inside uploads if we used that structure
            # (Current structure puts runs in output_dir, but older structure put them in uploads)
            
    except Exception as e:
        print(f"Cleanup error: {e}")

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/uploads")
def get_uploads():
    # Privacy: Do not list uploads
    return []

# Serve output files (including clips)
app.mount("/static", StaticFiles(directory=OUTPUT_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
