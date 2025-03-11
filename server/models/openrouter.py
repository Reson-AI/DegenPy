#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OpenRouterClient:
    """
    Client for OpenRouter API to access various AI models
    """
    
    def __init__(self):
        # 从.env文件中读取配置
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
            
        self.api_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
        self.default_model = os.getenv("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-3-opus:beta")
        self.default_max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", "1024"))
        self.default_temperature = float(os.getenv("OPENROUTER_TEMPERATURE", "0.7"))
        
    def generate_content(self, 
                         prompt: str, 
                         model: str = None, 
                         system_prompt: Optional[str] = None,
                         max_tokens: int = None,
                         temperature: float = None) -> Optional[str]:
        """
        Generate content using the specified model
        
        Args:
            prompt: The user prompt
            model: Model identifier
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
                
        Returns:
            Generated content or None if generation failed
        """
        try:
            # 使用提供的参数或默认值
            model = model or self.default_model
            max_tokens = max_tokens or self.default_max_tokens
            temperature = temperature or self.default_temperature
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": []
            }
            
            # Add system prompt if provided
            if system_prompt:
                payload["messages"].append({
                    "role": "system",
                    "content": system_prompt
                })
                
            # Add user prompt
            payload["messages"].append({
                "role": "user",
                "content": prompt
            })
            
            # Add generation parameters
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature
            
            # Make the API request
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                print(f"Error generating content: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception in content generation: {str(e)}")
            return None
            
    def process_with_agent(self, agent_config: Dict[str, Any], content: str) -> Optional[str]:
        """
        Process content using an agent's personality
        
        Args:
            agent_config: Agent configuration
            content: Content to process
                
        Returns:
            Processed content or None if processing failed
        """
        try:
            personality = agent_config.get("personality", {})
            prompt_template = personality.get("prompt_template", "Respond to the following: {{content}}")
            
            # Replace the content placeholder in the template
            prompt = prompt_template.replace("{{content}}", content)
            
            # Create a system prompt based on the agent's personality
            system_prompt = f"You are a {agent_config.get('name', 'AI assistant')}. "
            
            if "speaking_style" in personality:
                system_prompt += f"Your speaking style is {personality['speaking_style']}. "
                
            if "tone" in personality:
                system_prompt += f"Your tone is {personality['tone']}. "
                
            if "catchphrases" in personality:
                catchphrases = ", ".join([f'"{phrase}"' for phrase in personality["catchphrases"]])
                system_prompt += f"You often use phrases like {catchphrases}. "
                
            if "interests" in personality:
                interests = ", ".join(personality["interests"])
                system_prompt += f"Your interests include {interests}. "
            
            # Generate content with the model
            return self.generate_content(
                prompt=prompt,
                system_prompt=system_prompt,
                # 使用默认配置，但对于代理人格处理我们使用稍高的温度
                max_tokens=self.default_max_tokens,
                temperature=0.8  # 有意使用稍高的温度来增加创造性
            )
            
        except Exception as e:
            print(f"Exception processing with agent: {str(e)}")
            return None
            
# Singleton instance
client = OpenRouterClient()

def generate_content(prompt: str, model: str = None, system_prompt: Optional[str] = None, 
                   max_tokens: int = None, temperature: float = None) -> Optional[str]:
    """
    Generate content using the specified model
    
    Args:
        prompt: The user prompt
        model: Model identifier (optional, uses default from .env if not provided)
        system_prompt: Optional system prompt
        max_tokens: Maximum tokens to generate (optional, uses default from .env if not provided)
        temperature: Temperature for generation (optional, uses default from .env if not provided)
            
    Returns:
        Generated content or None if generation failed
    """
    return client.generate_content(prompt, model, system_prompt, max_tokens, temperature)

def process_with_agent(agent_config: Dict[str, Any], content: str) -> Optional[str]:
    """
    Process content using an agent's personality
    
    Args:
        agent_config: Agent configuration
        content: Content to process
            
    Returns:
        Processed content or None if processing failed
    """
    return client.process_with_agent(agent_config, content)

if __name__ == "__main__":
    # Example usage
    agent_config = {
        "name": "Trump XBT",
        "description": "A character that mimics Donald Trump's speaking style with a focus on cryptocurrency",
        "personality": {
            "speaking_style": "Bombastic, uses simple words, lots of superlatives",
            "catchphrases": ["Tremendous", "Huge", "The best"],
            "interests": ["Bitcoin", "Cryptocurrency", "Finance"],
            "tone": "Confident, assertive",
            "prompt_template": "Respond to this information about cryptocurrency in Trump's style: {{content}}"
        }
    }
    
    content = "Bitcoin price has increased by 15% this week, reaching a new all-time high."
    
    result = process_with_agent(agent_config, content)
    print(result)
