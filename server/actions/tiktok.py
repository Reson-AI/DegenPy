#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TikTokPublisher:
    """
    Publish content to TikTok
    """
    
    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        
        if not self.client_key or not self.client_secret:
            raise ValueError("TikTok API credentials not configured")
            
        self.api_base_url = "https://open.tiktokapis.com/v2"
        self.access_token = None
        self.token_expiry = 0
        
    def _get_access_token(self) -> bool:
        """
        Get or refresh the access token
        
        Returns:
            True if token was obtained successfully, False otherwise
        """
        # Check if we have a valid token
        if self.access_token and time.time() < self.token_expiry - 300:  # 5 min buffer
            return True
            
        try:
            # Request a new token
            response = requests.post(
                f"{self.api_base_url}/oauth/token",
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "video.upload video.publish"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                # Set expiry time (convert expires_in from seconds to timestamp)
                self.token_expiry = time.time() + data.get("expires_in", 3600)
                return True
            else:
                print(f"Failed to get TikTok access token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Exception getting TikTok access token: {str(e)}")
            return False
            
    def publish_video(self, video_url: str, caption: str, hashtags: Optional[list] = None) -> Tuple[bool, Optional[str]]:
        """
        Publish a video to TikTok
        
        Args:
            video_url: URL to the video file
            caption: Caption for the video
            hashtags: List of hashtags to include
                
        Returns:
            Tuple of (success, post_url)
                success: True if video was published successfully
                post_url: URL to the published video or None if failed
        """
        # Ensure we have a valid token
        if not self._get_access_token():
            return False, None
            
        try:
            # Download the video first
            video_data = self._download_video(video_url)
            if not video_data:
                return False, None
                
            # Prepare the caption with hashtags
            if hashtags:
                hashtag_text = " ".join(hashtags)
                full_caption = f"{caption} {hashtag_text}"
            else:
                full_caption = caption
                
            # Upload the video
            upload_response = self._upload_video(video_data)
            if not upload_response:
                return False, None
                
            # Publish the video
            video_id = upload_response.get("video_id")
            publish_response = self._publish_video(video_id, full_caption)
            
            if publish_response:
                post_id = publish_response.get("post_id")
                post_url = f"https://www.tiktok.com/@username/video/{post_id}"  # Replace username with actual username
                return True, post_url
            else:
                return False, None
                
        except Exception as e:
            print(f"Exception publishing video to TikTok: {str(e)}")
            return False, None
            
    def _download_video(self, video_url: str) -> Optional[bytes]:
        """
        Download a video from a URL
        
        Args:
            video_url: URL to the video
                
        Returns:
            Video data as bytes or None if download failed
        """
        try:
            response = requests.get(video_url, stream=True)
            if response.status_code == 200:
                return response.content
            else:
                print(f"Failed to download video: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception downloading video: {str(e)}")
            return None
            
    def _upload_video(self, video_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Upload a video to TikTok
        
        Args:
            video_data: Video data as bytes
                
        Returns:
            Response data or None if upload failed
        """
        try:
            # This is a simplified implementation
            # In a real implementation, you would need to follow TikTok's chunked upload protocol
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "video/mp4"
            }
            
            response = requests.post(
                f"{self.api_base_url}/video/upload",
                headers=headers,
                data=video_data
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to upload video: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception uploading video: {str(e)}")
            return None
            
    def _publish_video(self, video_id: str, caption: str) -> Optional[Dict[str, Any]]:
        """
        Publish an uploaded video
        
        Args:
            video_id: ID of the uploaded video
            caption: Caption for the video
                
        Returns:
            Response data or None if publishing failed
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "video_id": video_id,
                "caption": caption,
                "visibility_type": "PUBLIC"
            }
            
            response = requests.post(
                f"{self.api_base_url}/video/publish",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to publish video: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception publishing video: {str(e)}")
            return None

# Singleton instance
publisher = TikTokPublisher()

def publish_to_tiktok(video_url: str, caption: str, hashtags: Optional[list] = None) -> Tuple[bool, Optional[str]]:
    """
    Publish a video to TikTok
    
    Args:
        video_url: URL to the video file
        caption: Caption for the video
        hashtags: List of hashtags to include
            
    Returns:
        Tuple of (success, post_url)
            success: True if video was published successfully
            post_url: URL to the published video or None if failed
    """
    return publisher.publish_video(video_url, caption, hashtags)

if __name__ == "__main__":
    # Example usage
    success, post_url = publish_to_tiktok(
        video_url="https://example.com/video.mp4",
        caption="Bitcoin is doing amazing things today!",
        hashtags=["#Bitcoin", "#Crypto", "#TrumpTalks"]
    )
    
    if success:
        print(f"Video published successfully: {post_url}")
    else:
        print("Failed to publish video")
