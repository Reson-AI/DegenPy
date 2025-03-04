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

class TwitterPublisher:
    """
    Publish content to Twitter/X
    """
    
    def __init__(self):
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_secret = os.getenv("TWITTER_ACCESS_SECRET")
        
        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            raise ValueError("Twitter API credentials not configured")
            
        self.api_base_url = "https://api.twitter.com/2"
        self.oauth_token = None
        self.token_expiry = 0
        
    def _get_oauth_token(self) -> bool:
        """
        Get or refresh the OAuth token
        
        Returns:
            True if token was obtained successfully, False otherwise
        """
        # Check if we have a valid token
        if self.oauth_token and time.time() < self.token_expiry - 300:  # 5 min buffer
            return True
            
        try:
            # OAuth 1.0a authentication for Twitter API v2
            # This is a simplified implementation
            # In a real implementation, you would use a proper OAuth library
            
            auth_url = "https://api.twitter.com/oauth2/token"
            auth = (self.api_key, self.api_secret)
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(auth_url, auth=auth, data=data)
            
            if response.status_code == 200:
                data = response.json()
                self.oauth_token = data.get("access_token")
                # Set expiry time (typically 2 hours)
                self.token_expiry = time.time() + 7200
                return True
            else:
                print(f"Failed to get Twitter OAuth token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Exception getting Twitter OAuth token: {str(e)}")
            return False
            
    def post_tweet(self, text: str, media_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Post a tweet, optionally with media
        
        Args:
            text: Tweet text content
            media_url: Optional URL to media (image or video)
                
        Returns:
            Tuple of (success, tweet_url)
                success: True if tweet was posted successfully
                tweet_url: URL to the posted tweet or None if failed
        """
        # Ensure we have a valid token
        if not self._get_oauth_token():
            return False, None
            
        try:
            headers = {
                "Authorization": f"Bearer {self.oauth_token}",
                "Content-Type": "application/json"
            }
            
            payload = {"text": text}
            
            # If media is provided, upload it first
            if media_url:
                media_id = self._upload_media(media_url)
                if media_id:
                    payload["media"] = {"media_ids": [media_id]}
                else:
                    print("Failed to upload media, proceeding with text-only tweet")
            
            # Post the tweet
            response = requests.post(
                f"{self.api_base_url}/tweets",
                headers=headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                tweet_id = data.get("data", {}).get("id")
                tweet_url = f"https://twitter.com/user/status/{tweet_id}"  # Replace 'user' with actual username
                return True, tweet_url
            else:
                print(f"Failed to post tweet: {response.status_code} - {response.text}")
                return False, None
                
        except Exception as e:
            print(f"Exception posting tweet: {str(e)}")
            return False, None
            
    def _upload_media(self, media_url: str) -> Optional[str]:
        """
        Upload media to Twitter
        
        Args:
            media_url: URL to the media file
                
        Returns:
            Media ID or None if upload failed
        """
        try:
            # Download the media first
            media_data = self._download_media(media_url)
            if not media_data:
                return None
                
            # Determine content type based on URL extension
            content_type = "video/mp4"  # Default to video
            if media_url.lower().endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif media_url.lower().endswith(".png"):
                content_type = "image/png"
            elif media_url.lower().endswith(".gif"):
                content_type = "image/gif"
                
            # Upload to Twitter media endpoint
            upload_url = "https://upload.twitter.com/1.1/media/upload.json"
            
            # For simplicity, we're using a single request upload
            # For larger files, you should use the chunked upload API
            
            headers = {
                "Authorization": f"OAuth oauth_consumer_key=\"{self.api_key}\", oauth_token=\"{self.access_token}\""
            }
            
            files = {
                "media": (
                    "media",
                    media_data,
                    content_type
                )
            }
            
            response = requests.post(upload_url, headers=headers, files=files)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("media_id_string")
            else:
                print(f"Failed to upload media: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception uploading media: {str(e)}")
            return None
            
    def _download_media(self, media_url: str) -> Optional[bytes]:
        """
        Download media from a URL
        
        Args:
            media_url: URL to the media
                
        Returns:
            Media data as bytes or None if download failed
        """
        try:
            response = requests.get(media_url, stream=True)
            if response.status_code == 200:
                return response.content
            else:
                print(f"Failed to download media: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception downloading media: {str(e)}")
            return None

# Singleton instance
publisher = TwitterPublisher()

def post_to_twitter(text: str, media_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Post a tweet, optionally with media
    
    Args:
        text: Tweet text content
        media_url: Optional URL to media (image or video)
            
    Returns:
        Tuple of (success, tweet_url)
            success: True if tweet was posted successfully
            tweet_url: URL to the posted tweet or None if failed
    """
    return publisher.post_tweet(text, media_url)

if __name__ == "__main__":
    # Example usage
    success, tweet_url = post_to_twitter(
        text="Bitcoin is doing amazing things today! #Bitcoin #Crypto",
        media_url="https://example.com/video.mp4"
    )
    
    if success:
        print(f"Tweet posted successfully: {tweet_url}")
    else:
        print("Failed to post tweet")
