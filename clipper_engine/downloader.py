import os
import yt_dlp
from pathlib import Path
import imageio_ffmpeg

def download_video(url: str, output_dir: str = "downloads") -> dict:
    """
    Downloads a video from a given URL using yt-dlp.
    Returns a dictionary with paths to the video file and metadata.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Configure yt-dlp to download best video+audio and merge them
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe()
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get('id')
        ext = info.get('ext')
        if not ext:
            # Fallback if ext isn't directly in info (can happen with merges)
            ext = 'mp4'
            
        file_path = os.path.join(output_dir, f"{video_id}.{ext}")
        
        return {
            "video_path": os.path.abspath(file_path),
            "title": info.get('title'),
            "duration": info.get('duration'),
            "id": video_id
        }

if __name__ == "__main__":
    # Test stub
    import sys
    if len(sys.argv) > 1:
        print(download_video(sys.argv[1]))
