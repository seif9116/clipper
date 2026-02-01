import os
import subprocess
import tempfile
import math
from typing import List, Dict, Any, Optional, Callable
import imageio_ffmpeg

# Set ffmpeg path for pydub before importing it to avoid RuntimeWarning
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

from pydub import AudioSegment
from openai import OpenAI

class Transcriber:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.ffmpeg_path = ffmpeg_path
        # Redundant safety, but good to keep
        AudioSegment.converter = self.ffmpeg_path

    def _convert_to_wav(self, input_path: str, output_path: str):
        """Converts input video/audio to wav using imageio-ffmpeg binary."""
        # Use -y to overwrite, -vn to disable video, -ac 1 for mono, -ar 16000 for 16kHz
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            output_path
        ]
        # Run silently
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def transcribe(self, audio_path: str, progress_callback: Optional[Callable[[int], None]] = None) -> List[Dict[str, Any]]:
        """
        Transcribes the audio file using OpenAI Whisper API in chunks.
        Returns a list of segments (start, end, text).
        """
        if progress_callback:
            progress_callback(0)

        print(f"Preparing audio from {audio_path}...")
        
        # Create temp directory for chunks and wav conversion
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "temp_audio.wav")
            
            try:
                # 1. Convert to WAV (Mono 16kHz is efficient and sufficient for Whisper)
                self._convert_to_wav(audio_path, wav_path)
                
                # 2. Load Audio
                print("Loading audio into memory...")
                # Verify file exists and has size
                if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                    raise Exception("Failed to convert audio or empty file produced.")
                    
                audio = AudioSegment.from_wav(wav_path)
                duration_ms = len(audio)
                
                # 3. Chunking (2 minutes = 120000 ms)
                chunk_length_ms = 2 * 60 * 1000
                total_chunks = math.ceil(duration_ms / chunk_length_ms)
                
                full_transcript = []
                
                print(f"Transcribing in {total_chunks} chunks...")
                
                for i in range(total_chunks):
                    start_ms = i * chunk_length_ms
                    end_ms = min((i + 1) * chunk_length_ms, duration_ms)
                    chunk = audio[start_ms:end_ms]
                    
                    # Ensure chunk is not empty
                    if len(chunk) == 0:
                        continue
                        
                    chunk_filename = os.path.join(temp_dir, f"chunk_{i}.mp3")
                    # Export as mp3 to keep upload size small for API
                    chunk.export(chunk_filename, format="mp3")
                    
                    # Transcribe chunk
                    with open(chunk_filename, "rb") as audio_file:
                        transcript = self.client.audio.transcriptions.create(
                            model="whisper-1", 
                            file=audio_file, 
                            response_format="verbose_json",
                            timestamp_granularities=["segment"]
                        )
                    
                    # Process segments
                    chunk_offset_sec = start_ms / 1000.0
                    
                    if hasattr(transcript, 'segments'):
                        for segment in transcript.segments:
                            # OpenAI Python library v1+ returns objects, not dicts for segments
                            full_transcript.append({
                                "start": segment.start + chunk_offset_sec,
                                "end": segment.end + chunk_offset_sec,
                                "text": segment.text.strip()
                            })
                    else:
                        # Fallback
                        full_transcript.append({
                            "start": chunk_offset_sec,
                            "end": chunk_offset_sec + transcript.duration,
                            "text": transcript.text or ""
                        })

                    # Update progress
                    percent = int(((i + 1) / total_chunks) * 100)
                    if progress_callback:
                        progress_callback(percent)
                        
            except Exception as e:
                print(f"Error during chunked transcription: {e}")
                # Fallback to original whole-file method if chunking fails? 
                # Or just re-raise. Let's re-raise to be safe.
                raise e

        # Final 100% check
        if progress_callback:
            progress_callback(100)
            
        return full_transcript

    @staticmethod
    def to_text_block(segments):
        """
        Converts segments to a string block with timestamps for the LLM.
        Format: [00:12-00:15] Hello world
        """
        text_block = ""
        for seg in segments:
            # Handle float vs int
            start_sec = int(seg.get('start', 0))
            end_sec = int(seg.get('end', 0))
            
            start = f"{start_sec // 60:02d}:{start_sec % 60:02d}"
            end = f"{end_sec // 60:02d}:{end_sec % 60:02d}"
            text = seg.get('text', '')
            text_block += f"[{start}-{end}] {text}\n"
        return text_block
