import os
import time
import shutil
import gc
from typing import List, Dict, Callable
from .downloader import download_video
from .transcriber import Transcriber
from .analyzer import ContentAnalyzer
from .compositor import Compositor
import imageio_ffmpeg

class ClipperPipeline:
    def __init__(self, output_base_dir: str, api_key: str, openai_key: str = None):
        self.output_base = output_base_dir
        self.api_key = api_key
        self.openai_key = openai_key
        
    def run(self, input_path: str, progress_callback: Callable[[str], None] = None, specific_run_dir: str = None) -> List[str]:
        """
        Runs the full pipeline on the input_path (URL or file).
        """
        if progress_callback: progress_callback("initializing")
        
        # 0. Setup
        if specific_run_dir:
            run_dir = specific_run_dir
        else:
            run_id = f"run_{int(time.time())}"
            run_dir = os.path.join(self.output_base, run_id)
            
        raw_dir = os.path.join(run_dir, "raw")
        clips_dir = os.path.join(run_dir, "clips")
        os.makedirs(raw_dir, exist_ok=True)
        
        # If we are regenerating in a specific dir, clean up old clips first
        if specific_run_dir:
             if os.path.exists(clips_dir):
                shutil.rmtree(clips_dir)
             
             json_path = os.path.join(run_dir, "clips.json")
             if os.path.exists(json_path):
                 os.remove(json_path)
            
        os.makedirs(clips_dir, exist_ok=True)
        
        # 1. Download / Ingest
        if progress_callback: progress_callback("downloading")
        
        if os.path.exists(input_path):
            # It's a local file
            video_path = input_path
            # We might want to copy it to raw_dir or just reference it
        else:
            # Assume URL
            meta = download_video(input_path, output_dir=raw_dir)
            video_path = meta['video_path']
            
        # 2. Transcribe
        transcript_cache_path = video_path + ".transcript.txt"
        transcript_text = ""
        
        if os.path.exists(transcript_cache_path):
             print(f"Found cached transcript at {transcript_cache_path}")
             if progress_callback: progress_callback("found cached transcript")
             with open(transcript_cache_path, "r") as f:
                 transcript_text = f.read()
        else:
            if progress_callback: progress_callback("transcribing: preparing...")
            
            def transcribe_progress(percent):
                if progress_callback:
                    progress_callback(f"transcribing: {percent}%")
                    
            # Use Whisper Transcriber
            from .transcriber import Transcriber
            transcriber = Transcriber(api_key=self.openai_key)
            segments = transcriber.transcribe(video_path, progress_callback=transcribe_progress)
            transcript_text = Transcriber.to_text_block(segments)
            
            # Cache it
            try:
                with open(transcript_cache_path, "w") as f:
                    f.write(transcript_text)
            except Exception as e:
                print(f"Warning: Could not save transcript cache: {e}")
        
        with open(os.path.join(run_dir, "transcript.txt"), "w") as f:
            f.write(transcript_text)
            
        # 3. Analyze
        if progress_callback: progress_callback("analyzing (transcript agent)")
        analyzer = ContentAnalyzer(api_key=self.api_key)
        
        clips_meta = analyzer.analyze_transcript(transcript_text)
        
        if not clips_meta:
            print("No clips found.")
            return []
            
        # 4. Render clips
        # Force garbage collection to free up memory from potentially large transcript/audio objects
        gc.collect()

        if progress_callback: progress_callback("rendering")
        compositor = Compositor(output_dir=clips_dir)

        generated_files = []

        for i, clip in enumerate(clips_meta):
            if progress_callback:
                progress_callback(f"rendering: {i+1}/{len(clips_meta)}")

            start_str = clip.get("start_time")
            end_str = clip.get("end_time")
            title = clip.get("title", "clip").replace(" ", "_")
            title = "".join(c if c.isalnum() or c in "_-" else "" for c in title)

            start_sec = ContentAnalyzer.seconds_from_str(start_str)
            end_sec = ContentAnalyzer.seconds_from_str(end_str)

            # Sanity check
            if end_sec <= start_sec:
                continue

            filename = f"clip_{i+1}_{title}.mp4"

            # Store filename in metadata for later retrieval
            clip["filename"] = filename

            out_path = compositor.render_clip(video_path, start_sec, end_sec, filename)
            generated_files.append(out_path)
            
        # Save metadata
        import json
        with open(os.path.join(run_dir, "clips.json"), "w") as f:
            json.dump(clips_meta, f, indent=2)

        if progress_callback: progress_callback("done")
        
        return generated_files
