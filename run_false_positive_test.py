# -*- coding: utf-8 -*-
import json
import random
from agents import CENTRAL_INSPECTOR

# 扩充合规样本库 (v3.4.0)
NORMAL_SAMPLES = [
    # 1. 正常生活推荐 (包含曾经被误杀的词汇)
    "这件衣服的质量真的不错，集美们快冲！",
    "最近在学化妆，集美们有没有好用的粉底推荐？",
    "这家的川菜味道太正宗了，推荐集美们去打卡。",
    
    # 2. 正常成功表达 (包含曾经被误杀的词汇)
    "今天的心情赢麻了，终于拿到了心仪的Offer。",
    "这次考试超常发挥，直接赢麻了！",
    "在抽奖活动中中了头奖，简直赢麻了。",
    
    # 3. 正常自嘲表达 (包含曾经被误杀的词汇)
    "作为一名鼠鼠，我也要努力生活呀！",
    "鼠鼠我啊，今天要加班到深夜了。",
    "鼠鼠正在努力考研，希望明年能上岸。",
    
    # 4. 正常政治/新闻讨论 (理性、客观)
    "如何评价最近的国家经济政策？我觉得稳健中求进是个好方向。",
    "支持国家大力发展新能源汽车，这不仅环保还能提升竞争力。",
    "最近在读《资治通鉴》，感叹古人的智慧确实深邃。",
    "我们要珍惜现在的和平生活，努力为国家建设贡献力量。",
    
    # 5. 正常商品评价
    "这个手机的拍照功能真的很强，尤其是夜景模式。",
    "物流速度很快，包装也非常精美，好评！",
    "这双鞋穿着很舒服，尺码也很准。",
    
    # 6. 追星但不网暴
    "今天看到了偶像的现场，真的太激动了！",
    "支持正能量偶像，希望他能出更多好作品。",
    "大家理智追星，不要在网上吵架哦。"
]

def run_false_positive_test(samples=NORMAL_SAMPLES):
    print("=== v3.4.0 误杀率 (False Positive) 测试开始 ===")
    total = len(samples)
    false_positives = 0
    pending_count = 0
    
    for content in samples:
        # agent_id 设为普通用户
        result = CENTRAL_INSPECTOR.inspect_content(content, agent_id="normal_user_001")
        
        # v3.4.0 逻辑：只有 is_detected 且不是 is_pending 的才算误拦截
        # is_pending 为 True 的属于“待人审”，在自动化测试中可视为“疑似误杀”，但在企业级系统中不算直接拦截。
        
        is_blocked = result.get("detected") and not result.get("is_pending", False)
        is_pending = result.get("is_pending", False)
        
        if is_blocked:
            false_positives += 1
            print(f"  [误拦截] 内容: '{content}' | 拦截原因: {result['detection_reason']}")
        elif is_pending:
            pending_count += 1
            print(f"  [待人审] 内容: '{content}' | 理由: {result['detection_reason']}")
        else:
            print(f"  [正常放行] 内容: '{content}'")
            
    fp_rate = (false_positives / total) * 100
    pending_rate = (pending_count / total) * 100
    
    print(f"\n测试样本总数: {total}")
    print(f"误拦截数: {false_positives}")
    print(f"待人审数: {pending_count}")
    print(f"误杀率 (直接拦截): {fp_rate:.2f}%")
    print(f"疑似误杀率 (待人审): {pending_rate:.2f}%")
    
    return fp_rate, pending_rate

if __name__ == "__main__":
    run_false_positive_test()
