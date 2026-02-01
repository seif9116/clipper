import os
import json
from typing import List, Dict, Any
from google import genai
from google.genai import types

class ContentAnalyzer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found. Please set it in environment or pass it in.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-3-flash-preview"


    def analyze_transcript(self, transcript_text: str) -> List[Dict]:
        """
        Analyzes the transcript using Gemini's Tool Use (Agentic) capability to robustly extract clips.
        """
        
        # Define the tool/function interface using explicit schema
        save_clips_tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="save_clips",
                    description="Saves the identified viral clips. Returns the list of clips found.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "clips": types.Schema(
                                type="ARRAY",
                                items=types.Schema(
                                    type="OBJECT",
                                    properties={
                                        "start_time": types.Schema(type="STRING", description="Start time in MM:SS format"),
                                        "end_time": types.Schema(type="STRING", description="End time in MM:SS format"),
                                        "title": types.Schema(type="STRING", description="Catchy hook title for the clip"),
                                        "transcript_text": types.Schema(type="STRING", description="The exact verbatim text content of the clip"),
                                        "reasoning": types.Schema(type="STRING", description="Explanation of why this is viral"),
                                        "score": types.Schema(type="INTEGER", description="Viral score from 0-100"),
                                    },
                                    required=["start_time", "end_time", "title", "transcript_text", "reasoning", "score"]
                                )
                            )
                        },
                        required=["clips"]
                    )
                )
            ]
        )

        prompt = """
        You are an expert video editing agent for TikTok and YouTube Shorts.
        Your goal is to analyze the provided transcript and identify exactly 25 of the most viral/engaging segments.
        
        CRITICAL RULES:
        1. **Duration**: Each clip MUST be between 30 and 60 seconds. Calculate the time difference between start_time and end_time to ensure this.
        2. **Self-Contained**: Clips must have a clear beginning and end thought. Do not cut sentences in half.
        3. **Content**: Look for actionable advice, specific tips, "aha" moments, strong opinions, or funny moments.
        4. **Transcript**: Copy the exact transcript text for the segment into the `transcript_text` field.
        
        EXAMPLES OF GREAT CONTENT:
        - Specific tips on how to study or take tests.
        - "The secret to..." or "Here's a tip..."
        - Intense or controversial opinions.
        
        INSTRUCTIONS:
        Analyze the transcript below, find the top 25 clips, and then call the `save_clips` tool with the list of clips.
        
        TRANSCRIPT:
        """ + transcript_text

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[save_clips_tool],
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode="ANY"
                        )
                    )
                )
            )
            
            # Extract tool call results
            # The SDK might auto-execute or we might need to parse.
            # Usually we inspect the function call args.
            
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    if fc.name == "save_clips":
                        # Convert Map/Struct to dict
                        # The SDK returns args as a dictionary-like object
                        args = fc.args
                        print(f"DEBUG: Model returned args: {args}")
                        
                        if "clips" in args:
                            raw_clips = args["clips"]
                            # Normalize keys just in case the model used camelCase
                            normalized_clips = []
                            for c in raw_clips:
                                new_c = c.copy()
                                # Handle common casing issues
                                if "startTime" in c and "start_time" not in c: new_c["start_time"] = c["startTime"]
                                if "endTime" in c and "end_time" not in c: new_c["end_time"] = c["endTime"]
                                if "transcriptText" in c and "transcript_text" not in c: new_c["transcript_text"] = c["transcriptText"]
                                normalized_clips.append(new_c)
                                
                            return normalized_clips
                            
            print("No function call found in agent response.")
            return []

        except Exception as e:
            print(f"Agent Analyzer Error: {e}")
            return []

    @staticmethod
    def seconds_from_str(time_str: str) -> float:
        """Converts MM:SS or HH:MM:SS to seconds"""
        if not time_str or not isinstance(time_str, str):
            print(f"Warning: Invalid time string: {time_str}")
            return 0.0
            
        try:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            return 0.0
        except Exception:
             print(f"Warning: Could not parse time: {time_str}")
             return 0.0

if __name__ == "__main__":
    pass
