import subprocess
import os
import imageio_ffmpeg

class Compositor:
    def __init__(self, output_dir="clips"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def render_clip(self, video_path: str, start_time: float, end_time: float, output_filename: str):
        """
        Renders a single clip by trimming the video without re-encoding when possible.
        """
        output_path = os.path.join(self.output_dir, output_filename)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(end_time - start_time),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental", 
            "-b:a", "192k",
            output_path
        ]

        print(f"Rendering to {output_path}...")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_path

if __name__ == "__main__":
    pass
