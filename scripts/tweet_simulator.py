#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import random
import requests
import datetime
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# API URL
WAREHOUSE_API_URL = os.getenv("WAREHOUSE_API_URL", "http://localhost:8000")

# 推文相关配置

# 推文内容模板
TWEET_TEMPLATES = [
    "今天的市场真是{sentiment}，{stock}的表现尤为突出。我认为这是因为{reason}。",
    "刚刚宣布了一项重大决定：{announcement}。这将对{impact_area}产生深远影响。",
    "我们的新产品{product}即将发布！这是{industry}领域的一次革命性突破。",
    "关于{topic}的讨论越来越热烈，我认为{opinion}。",
    "今天与{person}进行了一次很有启发性的交流，讨论了{discussion_topic}的问题。",
    "我对{event}感到{emotion}。这对{affected_party}意味着什么？",
    "刚刚读完一本关于{book_topic}的好书，强烈推荐给对{interest_area}感兴趣的人。",
    "我们需要更多关注{social_issue}。是时候采取行动了！",
    "对于{controversy}的争议，我的立场是{stance}。",
    "预测：未来五年内，{prediction}将成为现实。"
]

# 填充推文模板的词汇
TWEET_VOCABULARY = {
    "sentiment": ["令人兴奋", "令人担忧", "出乎意料", "平淡无奇", "充满希望"],
    "stock": ["特斯拉", "苹果", "亚马逊", "谷歌", "微软", "Facebook", "Twitter", "比特币"],
    "reason": ["市场情绪波动", "新政策影响", "技术突破", "全球经济形势", "行业竞争格局变化"],
    "announcement": ["新的合作伙伴关系", "重大收购", "战略转型", "管理层变动", "全新商业模式"],
    "impact_area": ["科技行业", "金融市场", "消费者行为", "全球供应链", "就业市场"],
    "product": ["AI助手", "电动汽车", "可穿戴设备", "虚拟现实头盔", "智能家居系统"],
    "industry": ["人工智能", "清洁能源", "太空探索", "生物技术", "数字货币"],
    "topic": ["气候变化", "数字隐私", "远程工作", "元宇宙", "去中心化金融"],
    "opinion": ["我们需要更多创新", "监管是必要的", "市场将自我调节", "这只是一时的热点", "这将彻底改变我们的生活方式"],
    "person": ["比尔·盖茨", "马克·扎克伯格", "蒂姆·库克", "马斯克", "拜登", "特朗普"],
    "discussion_topic": ["可持续发展", "数字转型", "太空商业化", "人工智能伦理", "未来教育"],
    "event": ["最新的技术突破", "市场波动", "政策变化", "全球峰会", "行业大会"],
    "emotion": ["乐观", "担忧", "兴奋", "谨慎", "惊讶"],
    "affected_party": ["创业者", "投资者", "消费者", "员工", "整个行业"],
    "book_topic": ["领导力", "创新", "未来趋势", "商业战略", "个人成长"],
    "interest_area": ["科技", "商业", "投资", "个人发展", "社会变革"],
    "social_issue": ["教育不平等", "气候行动", "数字鸿沟", "医疗可及性", "经济包容性"],
    "controversy": ["加密货币监管", "科技公司垄断", "人工智能安全", "数据隐私", "平台责任"],
    "stance": ["需要平衡监管与创新", "市场应该自由发展", "需要全球合作", "应该由专家决定", "需要更多公众参与"],
    "prediction": ["去中心化自治组织", "脑机接口普及", "太空旅游商业化", "通用人工智能", "碳中和经济"]
}

def generate_random_tweet():
    """生成一条随机推文"""
    # 随机选择推文模板
    template = random.choice(TWEET_TEMPLATES)
    
    # 填充模板
    for key, values in TWEET_VOCABULARY.items():
        if "{" + key + "}" in template:
            template = template.replace("{" + key + "}", random.choice(values))
    
    # 生成当前时间
    current_time = datetime.datetime.now().isoformat()
    
    # 创建推文数据
    tweet = {
        "time": current_time,
        "text": template
    }
    
    return tweet

def send_tweet_to_api(tweet, tags=None):
    """发送推文到API
    
    Args:
        tweet: 包含speaker、time和text的字典
        tags: 可选的标签列表或集合
        
    Returns:
        成功时返回API响应，失败时返回False
    """
    try:
        url = f"{WAREHOUSE_API_URL}/data"
        
        # 构建请求数据
        request_data = {
            "content": tweet
        }
        
        # 如果提供了标签，添加到请求中
        if tags:
            # 如果是集合，转换为列表
            if isinstance(tags, set):
                tags = list(tags)
            request_data["tags"] = tags
        
        response = requests.post(url, json=request_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"推文发送成功: {tweet['speaker']} - {tweet['text'][:30]}...")
            if tags:
                print(f"包含标签: {tags}")
            return result
        else:
            print(f"发送失败，状态码: {response.status_code}")
            print(f"请求URL: {url}")
            print(f"请求数据: {json.dumps(request_data, ensure_ascii=False)}")
            print(f"响应内容: {response.text}")
            try:
                return response.json()
            except:
                return False
    except Exception as e:
        print(f"发送推文时出错: {str(e)}")
        return False

def test_db_service(num_tweets=5, interval=1):
    """测试数据库服务
    
    Args:
        num_tweets: 要发送的推文数量
        interval: 发送间隔（秒）
    """
    print(f"开始测试数据库服务，将发送 {num_tweets} 条推文，间隔 {interval} 秒...")
    
    success_count = 0
    failed_count = 0
    sent_tweets = []
    
    # 首先测试API是否在线
    try:
        response = requests.get(f"{WAREHOUSE_API_URL}/")
        if response.status_code == 200:
            print(f"✅ API服务在线: {WAREHOUSE_API_URL}")
        else:
            print(f"❌ API服务返回异常状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到API服务: {str(e)}")
        print(f"请确保run.py已启动并且API服务正在运行")
        return False
    
    # 发送测试推文
    for i in range(num_tweets):
        try:
            print(f"\n发送测试推文 {i+1}/{num_tweets}...")
            
            # 生成随机推文
            tweet = generate_random_tweet()
            sent_tweets.append(tweet)
            
            # 发送到API
            result = send_tweet_to_api(tweet)
            
            if result and isinstance(result, dict) and result.get("status") == "success":
                success_count += 1
                print(f"✅ 推文 {i+1} 发送成功")
                print(f"  详细响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            else:
                failed_count += 1
                print(f"❌ 推文 {i+1} 发送失败")
                print(f"  详细响应: {json.dumps(result, ensure_ascii=False, indent=2) if result else 'None'}")
            
            # 等待指定间隔
            if i < num_tweets - 1:  # 最后一条不需要等待
                print(f"等待 {interval} 秒后发送下一条推文...")
                time.sleep(interval)
                
        except Exception as e:
            print(f"❌ 发送推文 {i+1} 时出错: {str(e)}")
            failed_count += 1
    
    # 打印测试结果
    print("\n==== 测试结果 ====")
    print(f"总计发送: {num_tweets} 条推文")
    print(f"成功: {success_count} 条")
    print(f"失败: {failed_count} 条")
    
    success_rate = (success_count / num_tweets) * 100 if num_tweets > 0 else 0
    print(f"成功率: {success_rate:.2f}%")
    
    if success_count > 0:
        print("\n数据库服务写入功能正常工作！✅")
        return True
    else:
        print("\n数据库服务写入功能异常，请检查配置和连接！❌")
        return False

def test_new_format(num_tweets=5, interval=1):
    """测试新格式的推文发送
    
    Args:
        num_tweets: 要发送的推文数量
        interval: 发送间隔（秒）
    """
    # 特别关注的标签
    special_tags = ["Trump", "Musk", "BTC"]
    
    # 其他常见标签
    other_tags = ["crypto", "AI", "tech", "finance", "politics", "news", 
                 "economy", "innovation", "market", "stocks", "ETH", 
                 "SOL", "XRP", "trading", "investment", "startup"]
    
    # 发言人列表
    speakers = ["@realDonaldTrump", "@elonmusk", "@SBF_FTX", "@VitalikButerin",
               "@jack", "@tim_cook", "@sundarpichai", "@satyanadella", 
               "@jeffbezos", "@richardbranson", "@jimcramer", "@warrenbuffett"]
    
    success_count = 0
    failed_count = 0
    
    print(f"\n开始测试新格式发送，将发送 {num_tweets} 条推文...")
    
    for i in range(num_tweets):
        try:
            # 随机选择发言人
            speaker = random.choice(speakers)
            
            # 生成推文内容
            tweet = generate_random_tweet()
            tweet["speaker"] = speaker
            
            # 生成随机标签列表，确保至少包含一个特别关注标签
            num_tags = random.randint(1, 4)  # 随机生成1-4个标签
            
            # 决定是否包含特别关注标签
            include_special = random.random() < 0.7  # 70%的概率包含特别关注标签
            
            tags = []
            if include_special:
                # 随机选择一个特别关注标签
                tags.append(random.choice(special_tags))
                
                # 添加其他随机标签
                remaining_tags = random.sample(other_tags, min(num_tags-1, len(other_tags)))
                tags.extend(remaining_tags)
            else:
                # 只使用其他标签
                tags = random.sample(other_tags, min(num_tags, len(other_tags)))
            
            print(f"\n发送第 {i+1}/{num_tweets} 条推文...")
            print(f"\u53d1言人: {speaker}")
            print(f"\u5185容: {tweet['text'][:50]}...")
            print(f"\u6807签: {tags}")
            
            # 发送推文
            result = send_tweet_to_api(tweet, tags)
            
            if result:
                success_count += 1
                print(f"\u2705 推文 {i+1} 发送成功!")
            else:
                failed_count += 1
                print(f"\u274c 推文 {i+1} 发送失败!")
            
            if i < num_tweets - 1:  # 最后一条不需要等待
                print(f"\u7b49待 {interval} 秒后发送下一条推文...")
                time.sleep(interval)
                
        except Exception as e:
            print(f"\u274c 发送推文 {i+1} 时出错: {str(e)}")
            failed_count += 1
    
    # 打印测试结果
    print("\n==== 测试结果 ====")
    print(f"总计发送: {num_tweets} 条推文")
    print(f"成功: {success_count} 条")
    print(f"失败: {failed_count} 条")
    
    success_rate = (success_count / num_tweets) * 100 if num_tweets > 0 else 0
    print(f"成功率: {success_rate:.2f}%")
    
    return success_count > 0

def main():
    """主函数 - 点击即可运行测试"""
    # 默认参数设置
    num_tweets = 5  # 默认发送5条推文
    interval = 1    # 默认间隔1秒
    
    # 直接运行新格式测试
    print("开始运行推文模拟器测试...")
    test_new_format(num_tweets, interval)

if __name__ == "__main__":
    main()
