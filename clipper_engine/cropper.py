import cv2
import mediapipe as mp
import numpy as np
import os

class SmartCropper:
    def __init__(self):
        # Use the modern Tasks API
        # We assume the model is in the same directory as this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, "blaze_face_short_range.tflite")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Face Detection model not found at {model_path}. Please download it.")

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        
        BaseOptions = python.BaseOptions
        FaceDetector = vision.FaceDetector
        FaceDetectorOptions = vision.FaceDetectorOptions
        VisionRunningMode = vision.RunningMode

        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.IMAGE) # Using IMAGE mode for frame-by-frame processing
        
        self.detector = FaceDetector.create_from_options(options)

    def get_crop_coordinates(self, video_path: str, start_time: float, end_time: float):
        """
        Analyzes the video segment and returns a list of crop centers (x_center) over time.
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        centers = []
        
        # Analyze every Nth frame to save time
        sample_rate = 5 
        
        current_frame = start_frame
        while current_frame < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
                
            if (current_frame - start_frame) % sample_rate == 0:
                # Convert BGR (OpenCV) to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Create MP Image
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                
                # Detect
                results = self.detector.detect(mp_image)
                
                if results.detections:
                    # Find largest face
                    # In Tasks API, format is different: list of Detection objects
                    # detection.bounding_box is boundingbox object
                    
                    largest_face = max(results.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                    bbox = largest_face.bounding_box
                    
                    # bbox properties: origin_x, origin_y, width, height (Integers in pixels)
                    # We need normalized 0-1 for our crop logic usually, or just pixel centers.
                    # My previous logic used normalized. Let's convert.
                    h, w, _ = frame.shape
                    
                    center_x_pixel = bbox.origin_x + (bbox.width / 2)
                    center_x_norm = center_x_pixel / w
                    
                    centers.append(center_x_norm)
                else:
                    centers.append(centers[-1] if centers else 0.5)
            
            current_frame += 1
            
        cap.release()
        
        if not centers:
            return 0.5 
            
        return float(np.median(centers))

if __name__ == "__main__":
    pass
