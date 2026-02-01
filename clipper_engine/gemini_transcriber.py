import os
import json
from typing import List, Dict, Any, Callable
from google import genai
from google.genai import types

class GeminiTranscriber:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Gemini API Key is required for transcription.")
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-1.5-flash" # Stable, fast, good multimodal

    def transcribe(self, video_path: str, progress_callback: Callable[[int], None] = None) -> List[Dict[str, Any]]:
        """
        Uploads the video directly to Gemini 1.5/2.0 and requests a timestamped transcription.
        """
        if progress_callback: progress_callback(10) # Started
        
        print(f"Uploading {video_path} to Gemini...")
        
        # 1. Upload file
        # Check if file is too large? Gemini handles up to 2GB usually via File API.
        try:
            # We use the media upload API
            file_ref = self.client.files.upload(file=video_path)
            
            if progress_callback: progress_callback(30) # Uploaded
            
            print(f"File uploaded: {file_ref.name}")
            
            # 2. Transcribe
            # We ask for a specific JSON structure to make parsing robust
            prompt = """
            Transcribe this video verbatim. 
            Output the transcript as a JSON array of objects, where each object has:
            - "start": start time in seconds (float)
            - "end": end time in seconds (float)
            - "text": the spoken text
            
            Example:
            [
              {"start": 0.0, "end": 2.5, "text": "Hello world."},
              {"start": 2.5, "end": 5.1, "text": "This is a test."}
            ]
            """
            
            if progress_callback: progress_callback(40) # Analyzing
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[file_ref, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if progress_callback: progress_callback(90) # Received
            
            # 3. Parse Response
            raw_json = response.text
            segments = json.loads(raw_json)
            
            if progress_callback: progress_callback(100)
            
            return segments

        except Exception as e:
            print(f"Gemini Transcription Failed: {e}")
            raise e
            
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
