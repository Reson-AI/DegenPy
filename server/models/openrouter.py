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
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
            
        self.api_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
        
    def generate_content(self, 
                         prompt: str, 
                         model: str = "anthropic/claude-3-opus:beta", 
                         system_prompt: Optional[str] = None,
                         max_tokens: int = 1024,
                         temperature: float = 0.7) -> Optional[str]:
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
                max_tokens=1024,
                temperature=0.8
            )
            
        except Exception as e:
            print(f"Exception processing with agent: {str(e)}")
            return None
            
    def fact_check(self, content: str) -> Dict[str, Any]:
        """
        Perform fact checking on content
        
        Args:
            content: Content to fact check
                
        Returns:
            Fact checking results
        """
        try:
            system_prompt = """
            You are a fact-checking assistant. Your task is to analyze the provided content and:
            1. Identify factual claims
            2. Assess the veracity of each claim
            3. Provide an overall assessment of the content's factual accuracy
            
            For each claim, indicate whether it is:
            - TRUE: Verified and accurate
            - LIKELY TRUE: Probably accurate but not fully verified
            - UNCERTAIN: Cannot be verified with available information
            - LIKELY FALSE: Probably inaccurate
            - FALSE: Verified to be inaccurate
            
            Return your analysis in JSON format.
            """
            
            prompt = f"Please fact-check the following content:\n\n{content}"
            
            result = self.generate_content(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.2
            )
            
            if result:
                # Try to parse the result as JSON
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    # If not valid JSON, return as text
                    return {"text": result, "format_error": True}
            else:
                return {"error": "Failed to generate fact check"}
                
        except Exception as e:
            print(f"Exception during fact checking: {str(e)}")
            return {"error": str(e)}

# Singleton instance
client = OpenRouterClient()

def generate_content(prompt: str, model: str = "anthropic/claude-3-opus:beta", system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Generate content using the specified model
    
    Args:
        prompt: The user prompt
        model: Model identifier
        system_prompt: Optional system prompt
            
    Returns:
        Generated content or None if generation failed
    """
    return client.generate_content(prompt, model, system_prompt)

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

def fact_check(content: str) -> Dict[str, Any]:
    """
    Perform fact checking on content
    
    Args:
        content: Content to fact check
            
    Returns:
        Fact checking results
    """
    return client.fact_check(content)

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
