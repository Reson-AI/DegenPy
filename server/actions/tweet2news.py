#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tweet2news")

# 加载环境变量
load_dotenv()

def generate_news_from_tweet(prompt: str) -> Optional[str]:
    """
    根据提示词将推文内容转换为新闻报道
    
    Args:
        prompt: 完整的提示词，包含指导模型如何生成新闻的指令
        
    Returns:
        生成的新闻内容，如果生成失败则返回None
    """
    try:
        
        # 读取OpenRouter配置
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("未找到OPENROUTER_API_KEY环境变量")
            return None
            
        api_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        model = os.getenv("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-3-opus:beta")
        max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", "1024"))
        temperature = float(os.getenv("OPENROUTER_TEMPERATURE", "0.7"))
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # 发送请求
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # 提取生成的内容
            if "choices" in result and len(result["choices"]) > 0:
                news_content = result["choices"][0]["message"]["content"]
                return news_content
            else:
                logger.error(f"API响应格式不正确: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {str(e)}")
            return None
        
    except Exception as e:
        logger.error(f"生成新闻失败: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    # 测试代码
    test_tweet = """
    特斯拉CEO埃隆·马斯克宣布，特斯拉将在2025年推出完全自动驾驶功能，并表示这将"彻底改变交通出行方式"。
    马斯克补充说："我们的AI技术已经超越了人类驾驶员的安全水平，数据显示事故率降低了40%。"
    """
    
    news = generate_news_from_tweet(test_tweet)
    print(news)
