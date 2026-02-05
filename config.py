# -*- coding: utf-8 -*-
"""
用户数字孪生风控Demo - 配置文件
"""

import os

# API配置 - 使用Gemini API
API_CONFIG = {
    "provider": "gemini",
    "api_key": os.getenv("GEMINI_API_KEY", "AIzaSyA3BK8OguVPVtz0J6YA7stqtWnido-Iv7Y"),
    "model": "gemini-2.0-flash"
}

# OpenAI兼容配置（备用）
OPENAI_CONFIG = {
    "base_url": "https://api.openai.com/v1",
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "model": "gpt-4o-mini"
}

# 风险类别定义
RISK_CATEGORIES = {
    "political": "政治敏感",
    "violence": "暴力血腥",
    "porn": "色情低俗",
    "illegal": "违法犯罪",
    "privacy": "隐私泄露",
    "misinformation": "虚假信息",
    "prompt_injection": "提示词注入",
    "jailbreak": "越狱攻击",
    "drugs": "违禁药物",
    "terrorism": "恐怖主义",
    "anti_social": "反党反社会",
    "historical_nihilism": "历史虚无"
}

# 风险等级
RISK_LEVELS = {
    0: "安全",
    1: "低风险",
    2: "中风险", 
    3: "高风险",
    4: "严重风险"
}
