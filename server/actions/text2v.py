#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Text2VideoGenerator:
    """
    Text to Video generation service
    """
    
    def __init__(self):
        self.api_url = os.getenv("TEXT2VIDEO_API_URL")
        if not self.api_url:
            raise ValueError("TEXT2VIDEO_API_URL environment variable not set")
            
    def generate(self, text: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Generate a video from text
        
        Args:
            text: The text content to convert to video
            config: Configuration for the video generation
                - style: Style of the video (news_report, trend_analysis, etc.)
                - duration: Target duration in seconds
                
        Returns:
            URL to the generated video or None if generation failed
        """
        try:
            # Prepare the request payload
            payload = {
                "text": text,
                "style": config.get("style", "default"),
                "duration": config.get("duration", 30),
                "resolution": config.get("resolution", "1080p"),
                "format": config.get("format", "mp4")
            }
            
            # Make the API request
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 202:
                # Asynchronous processing - get job ID
                job_id = response.json().get("job_id")
                return self._poll_job_status(job_id)
            elif response.status_code == 200:
                # Synchronous response
                return response.json().get("video_url")
            else:
                print(f"Error generating video: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception in text2video generation: {str(e)}")
            return None
            
    def _poll_job_status(self, job_id: str, max_attempts: int = 30, delay: int = 10) -> Optional[str]:
        """
        Poll for job completion
        
        Args:
            job_id: The job ID to poll
            max_attempts: Maximum number of polling attempts
            delay: Delay between polling attempts in seconds
            
        Returns:
            URL to the generated video or None if generation failed
        """
        status_url = f"{self.api_url}/status/{job_id}"
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(status_url)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status == "completed":
                        return data.get("video_url")
                    elif status == "failed":
                        print(f"Video generation failed: {data.get('error')}")
                        return None
                    else:
                        # Still processing
                        print(f"Video generation in progress ({attempt+1}/{max_attempts}): {status}")
                        time.sleep(delay)
                else:
                    print(f"Error checking job status: {response.status_code} - {response.text}")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"Exception while polling job status: {str(e)}")
                time.sleep(delay)
                
        print(f"Timed out waiting for video generation after {max_attempts} attempts")
        return None

# Singleton instance
generator = Text2VideoGenerator()

def generate_video(text: str, config: Dict[str, Any]) -> Optional[str]:
    """
    Generate a video from text content
    
    Args:
        text: The text content to convert to video
        config: Configuration for the video generation
            
    Returns:
        URL to the generated video or None if generation failed
    """
    return generator.generate(text, config)

if __name__ == "__main__":
    # Example usage
    config = {
        "style": "news_report",
        "duration": 30
    }
    
    sample_text = """
    Bitcoin has reached a new all-time high today, surpassing $70,000 for the first time.
    Analysts attribute this surge to increased institutional adoption and growing interest
    from traditional finance. This milestone comes after months of steady growth and
    represents a significant moment for cryptocurrency enthusiasts.
    """
    
    video_url = generate_video(sample_text, config)
    
    if video_url:
        print(f"Video generated successfully: {video_url}")
    else:
        print("Failed to generate video")
