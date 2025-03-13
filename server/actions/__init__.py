#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动作处理器模块
"""

from server.actions.webhook import WebhookAction
from server.actions.text2v import create_video
from server.actions.twitter import post_to_twitter
from server.actions.tiktok import publish_to_tiktok

# 导出动作函数和类
__all__ = [
    'WebhookAction',
    'create_video',
    'post_to_twitter',
    'publish_to_tiktok'
]
