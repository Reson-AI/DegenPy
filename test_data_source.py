#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import random
import logging
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_data_source")

# API 基础 URL
BASE_URL = "http://localhost:8000"

# 测试数据
FOLLOWED_SOURCES = [
    {
        "author_id": "crypto_expert",
        "content": "比特币今天突破了65000美元，这是历史新高！我认为这只是开始，未来几个月可能会看到更高的价格。机构投资者正在大量涌入。",
        "source_type": "followed"
    },
    {
        "author_id": "eth_developer",
        "content": "以太坊2.0的合并即将到来，这将显著降低能源消耗并提高交易速度。这是加密货币领域的一个重大里程碑。",
        "source_type": "followed"
    },
    {
        "author_id": "defi_analyst",
        "content": "DeFi总锁仓量突破1000亿美元。去中心化金融正在重塑传统金融体系，为用户提供更高的收益和更多的金融自由。",
        "source_type": "followed"
    }
]

TRENDING_SOURCES = [
    {
        "author_id": "crypto_news",
        "content": "#比特币 再创新高！市场情绪高涨，多家分析机构上调了年底价格预测。$BTC $ETH #加密货币",
        "source_type": "trending"
    },
    {
        "author_id": "market_watcher",
        "content": "加密市场总市值突破3万亿美元，创历史新高！各大主流币种普遍上涨，市场情绪非常乐观。#牛市 #加密货币",
        "source_type": "trending"
    },
    {
        "author_id": "nft_collector",
        "content": "NFT市场持续火爆，过去24小时交易量超过5亿美元。蓝筹NFT项目价格稳步上涨，新项目层出不穷。#NFT #数字艺术",
        "source_type": "trending"
    },
    {
        "author_id": "tech_news",
        "content": "多家科技巨头宣布进军元宇宙，加密货币和NFT将成为元宇宙经济的基础。#元宇宙 #Web3",
        "source_type": "trending"
    },
    {
        "author_id": "finance_expert",
        "content": "通货膨胀数据超出预期，投资者寻求加密货币作为对冲工具。比特币被视为'数字黄金'，吸引更多传统投资者。#通胀 #比特币",
        "source_type": "trending"
    }
]

OTHER_SOURCES = [
    {
        "author_id": "random_user",
        "content": "今天天气真好，适合出去走走。",
        "source_type": "other"
    },
    {
        "author_id": "news_bot",
        "content": "最新体育新闻：某足球队赢得了比赛。",
        "source_type": "other"
    }
]

def send_data(data):
    """发送数据到API
    
    Args:
        data: 要发送的数据
        
    Returns:
        响应对象
    """
    try:
        response = requests.post(f"{BASE_URL}/data", json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"发送数据时出错: {str(e)}")
        return None

def get_content(content_id):
    """获取指定ID的内容
    
    Args:
        content_id: 内容ID
        
    Returns:
        内容对象
    """
    try:
        response = requests.get(f"{BASE_URL}/content/{content_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"获取内容时出错: {str(e)}")
        return None

def get_recent_content(source_type=None, limit=50):
    """获取最近的内容
    
    Args:
        source_type: 来源类型
        limit: 限制数量
        
    Returns:
        内容列表
    """
    try:
        params = {}
        if source_type:
            params["source_type"] = source_type
        if limit:
            params["limit"] = limit
            
        response = requests.get(f"{BASE_URL}/recent-content", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"获取最近内容时出错: {str(e)}")
        return None

def test_data_submission():
    """测试数据提交功能"""
    logger.info("开始测试数据提交功能")
    
    # 发送关注人数据
    for data in FOLLOWED_SOURCES:
        result = send_data(data)
        if result and result.get("status") == "success":
            logger.info(f"成功发送关注人数据: {data['author_id']}")
        else:
            logger.error(f"发送关注人数据失败: {data['author_id']}")
    
    # 发送趋势数据
    for data in TRENDING_SOURCES:
        result = send_data(data)
        if result and result.get("status") == "success":
            logger.info(f"成功发送趋势数据: {data['author_id']}")
        else:
            logger.error(f"发送趋势数据失败: {data['author_id']}")
    
    # 发送其他数据
    for data in OTHER_SOURCES:
        result = send_data(data)
        if result and result.get("status") == "success":
            logger.info(f"成功发送其他数据: {data['author_id']}")
        else:
            logger.error(f"发送其他数据失败: {data['author_id']}")
    
    logger.info("数据提交测试完成")

def test_content_retrieval():
    """测试内容检索功能"""
    logger.info("开始测试内容检索功能")
    
    # 获取最近的所有内容
    result = get_recent_content()
    if result and result.get("status") == "success":
        contents = result.get("data", {}).get("contents", [])
        logger.info(f"成功获取 {len(contents)} 条最近内容")
        
        # 如果有内容，测试获取单个内容
        if contents:
            content_id = contents[0].get("id")
            content_result = get_content(content_id)
            if content_result and content_result.get("status") == "success":
                logger.info(f"成功获取内容 {content_id}")
            else:
                logger.error(f"获取内容 {content_id} 失败")
    else:
        logger.error("获取最近内容失败")
    
    # 测试按来源类型获取内容
    for source_type in ["followed", "trending", "other"]:
        result = get_recent_content(source_type)
        if result and result.get("status") == "success":
            contents = result.get("data", {}).get("contents", [])
            logger.info(f"成功获取 {len(contents)} 条 {source_type} 类型的内容")
        else:
            logger.error(f"获取 {source_type} 类型的内容失败")
    
    logger.info("内容检索测试完成")

def main():
    """主函数"""
    logger.info("开始测试数据源功能")
    
    # 测试数据提交
    test_data_submission()
    
    # 等待数据处理
    logger.info("等待数据处理...")
    time.sleep(2)
    
    # 测试内容检索
    test_content_retrieval()
    
    logger.info("数据源功能测试完成")

if __name__ == "__main__":
    main()
