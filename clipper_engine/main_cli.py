import argparse
import os
import sys
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        pass

# Add project root to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clipper_engine.downloader import download_video
from clipper_engine.transcriber import Transcriber
from clipper_engine.analyzer import ContentAnalyzer
from clipper_engine.cropper import SmartCropper
from clipper_engine.compositor import Compositor

def main():
    parser = argparse.ArgumentParser(description="AI Video Clipper - Turn long videos into viral shorts.")
    parser.add_argument("url", help="YouTube URL or local file path")
    parser.add_argument("--output", "-o", default="clipper_output", help="Output directory name")
    parser.add_argument("--api_key", help="Gemini API Key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM response for testing")
    
    args = parser.parse_args()
    
    # Load env vars
    load_dotenv()
    
    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key and not args.mock:
        print("Error: Gemini API Key is required. Set GEMINI_API_KEY env var or pass --api_key")
        return

    # 1. Download
    print(f"STEP 1: Downloading/Processing {args.url}...")
    # Should probably check if it's a URL or file. For now assuming URL.
    if os.path.exists(args.url):
        video_path = args.url
        video_metadata = {"title": "local_video", "id": "local"}
    else:
        video_metadata = download_video(args.url, output_dir=os.path.join(args.output, "raw"))
        video_path = video_metadata["video_path"]
    
    print(f"Video ready: {video_path}")

    # 2. Transcribe
    print("STEP 2: Transcribing...")
    transcriber = Transcriber()
    
    def on_progress(p):
        print(f"Transcribing: {p}%", end="\r")
        
    segments = transcriber.transcribe(video_path, progress_callback=on_progress)
    print() # Newline
    transcript_text = Transcriber.to_text_block(segments)
    
    # Save transcript for debug
    with open(os.path.join(args.output, "transcript.txt"), "w") as f:
        f.write(transcript_text)

    # 3. Analyze
    print("STEP 3: Analyzing for viral clips...")
    
    if args.mock:
        print(" [MOCK MODE] returning dummy clips...")
        # Create a dummy clip from 0s to 15s (or end of video)
        clips = [{
            "start_time": "00:00",
            "end_time": "00:15",
            "title": "Test Clip",
            "score": 100
        }]
    else:
        analyzer = ContentAnalyzer(api_key=api_key)
        clips = analyzer.analyze_transcript(transcript_text)
    
    if not clips:
        print("No clips found by LLM.")
        return

    print(f"Found {len(clips)} clips:")
    for c in clips:
        print(f" - {c.get('title')} ({c.get('start_time')} - {c.get('end_time')}) Score: {c.get('score')}")

    # 4. Crop & Render
    print("STEP 4: Cropping and Rendering...")
    cropper = SmartCropper()
    compositor = Compositor(output_dir=os.path.join(args.output, "clips"))
    
    for i, clip in enumerate(clips):
        start_str = clip["start_time"]
        end_str = clip["end_time"]
        
        # Convert times to seconds
        start_sec = ContentAnalyzer.seconds_from_str(start_str)
        end_sec = ContentAnalyzer.seconds_from_str(end_str)
        
        print(f"Processing Clip {i+1}: {clip.get('title')}...")
        
        # Get crop center
        crop_center = cropper.get_crop_coordinates(video_path, start_sec, end_sec)
        
        # Render
        filename = f"clip_{i+1}_{clip.get('title').replace(' ', '_')}.mp4"
        compositor.render_clip(video_path, start_sec, end_sec, filename)
        
    print("Done! Clips saved.")

if __name__ == "__main__":
    main()
