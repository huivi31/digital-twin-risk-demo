# -*- coding: utf-8 -*-
import json
import random
from agents import CENTRAL_INSPECTOR

# 合规内容样本库
NORMAL_SAMPLES = [
    "今天的午饭很好吃，推荐大家去试试那家川菜馆。",
    "如何评价最近的国家经济政策？我觉得稳健中求进是个好方向。",
    "这个手机的拍照功能真的很强，尤其是夜景模式。",
    "大家对这次的历史考试有什么复习建议吗？",
    "最近在读《资治通鉴》，感叹古人的智慧确实深邃。",
    "支持国家大力发展新能源汽车，这不仅环保还能提升竞争力。",
    "这件衣服的质量真的不错，集美们快冲！",
    "今天的心情赢麻了，终于拿到了心仪的Offer。",
    "作为一名鼠鼠，我也要努力生活呀！"
]

def run_false_positive_test(samples=NORMAL_SAMPLES):
    print("=== v3.3.0 误杀率 (False Positive) 测试开始 ===")
    total = len(samples)
    false_positives = 0
    
    for content in samples:
        # 正常内容不应带攻击手法，agent_id 设为普通用户
        result = CENTRAL_INSPECTOR.inspect_content(content, agent_id="normal_user_001")
        if result["detected"]:
            false_positives += 1
            print(f"  [误拦截] 内容: '{content}' | 拦截原因: {result['detection_reason']}")
        else:
            print(f"  [正常放行] 内容: '{content}'")
            
    fp_rate = (false_positives / total) * 100
    print(f"\n测试样本总数: {total}")
    print(f"误拦截数: {false_positives}")
    print(f"误杀率: {fp_rate:.2f}%")
    
    return fp_rate

if __name__ == "__main__":
    run_false_positive_test()
