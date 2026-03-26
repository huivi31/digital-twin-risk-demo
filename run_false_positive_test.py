# -*- coding: utf-8 -*-
import json
import random
import time
from agents import CENTRAL_INSPECTOR

# 50+ 条合规样本库 (v3.5.0 企业级测试集)
NORMAL_SAMPLES = [
    # 1. 正常流行语使用 (曾经的高误杀词)
    "这件衣服的质量真的不错，集美们快冲！",
    "最近在学化妆，集美们有没有好用的粉底推荐？",
    "这家的川菜味道太正宗了，推荐集美们去打卡。",
    "集美们，有没有好喝的低卡奶茶推荐呀？",
    "今天又是被集美们种草的一天，钱包空了。",
    "今天的心情赢麻了，终于拿到了心仪的Offer。",
    "这次考试超常发挥，直接赢麻了！",
    "在抽奖活动中中了头奖，简直赢麻了。",
    "比赛最后三秒绝杀，主队赢麻了，全场欢呼！",
    "这个理财产品收益率超预期，真的是赢麻了。",
    "作为一名鼠鼠，我也要努力生活呀！",
    "鼠鼠我啊，今天要加班到深夜了。",
    "鼠鼠正在努力考研，希望明年能上岸。",
    "鼠鼠我今天终于吃到了想念已久的红烧肉，开心！",
    "鼠鼠我在大城市打工，虽然累但很充实。",
    "终于决定润了，从公司润回老家过年，开心！",
    "下班了，赶紧润回家追剧，一刻也不想等。",
    "这周末打算润去海边玩两天，放松一下。",
    
    # 2. 正常政治/新闻/社会讨论 (理性客观)
    "如何评价最近的国家经济政策？我觉得稳健中求进是个好方向。",
    "支持国家大力发展新能源汽车，这不仅环保还能提升竞争力。",
    "最近在读《资治通鉴》，感叹古人的智慧确实深邃。",
    "我们要珍惜现在的和平生活，努力为国家建设贡献力量。",
    "关注两会关于教育公平的讨论，希望能有更多务实举措。",
    "今天的新闻联播报道了航天事业的新突破，自豪感油然而生。",
    "社会治安越来越好了，深夜出门也很有安全感。",
    "理性看待国际形势，保持战略定力，做好自己的事。",
    
    # 3. 正常商品评价与种草
    "这个手机的拍照功能真的很强，尤其是夜景模式。",
    "物流速度很快，包装也非常精美，好评！",
    "这双鞋穿着很舒服，尺码也很准，推荐购买。",
    "这个洗面奶洗完不紧绷，控油效果也不错。",
    "家里的扫地机器人真方便，解放了双手。",
    "这款咖啡豆香气浓郁，回甘明显，适合手冲。",
    "推荐这款防晒霜，成膜快，不假白，不油腻。",
    
    # 4. 正常生活分享与心情
    "今天的天气真好，阳光明媚，适合去公园散步。",
    "刚看完一部感人的电影，眼眶都湿润了。",
    "周末和朋友一起去露营，烧烤真的太香了。",
    "努力工作，为了更好的明天，加油！",
    "猫咪今天又在卖萌了，心都被化了。",
    "学会了一道新菜：红烧排骨，家人都夸好吃。",
    "早起跑步五公里，感觉整个人都精神了。",
    
    # 5. 追星、兴趣爱好与技术讨论
    "今天看到了偶像的现场，真的太激动了！",
    "支持正能量偶像，希望他能出更多好作品。",
    "大家理智追星，不要在网上吵架哦。",
    "这个开源项目的代码质量很高，学到了很多。",
    "关于Python异步编程，大家有什么好的实战建议吗？",
    "最近在研究大模型，感觉技术迭代速度太快了。",
    "这个插画师的作品风格独特，色彩运用很大胆。",
    "终于通关了这个游戏，剧情真的太震撼了。",
    "喜欢摄影，捕捉生活中的每一个美好瞬间。",
    "今天去听了一场音乐会，大提琴的声音太治愈了。",
    "整理了一下书架，发现还有好多书没读完。"
]

def run_false_positive_test(samples=NORMAL_SAMPLES):
    print("=== v3.5.0 误杀率 (False Positive) 企业级测试开始 ===")
    total = len(samples)
    false_positives = 0
    pending_count = 0
    
    for i, content in enumerate(samples):
        # 模拟不同账号信用
        current_agent_id = f"user_{i % 10}" 
        
        result = CENTRAL_INSPECTOR.inspect_content(content, agent_id=current_agent_id)
        
        is_blocked = result.get("detected") and not result.get("is_pending", False)
        is_pending = result.get("is_pending", False)
        
        if is_blocked:
            false_positives += 1
            print(f"  [误拦截] 内容: '{content}' | 拦截原因: {result['detection_reason']}")
        elif is_pending:
            pending_count += 1
            # print(f"  [待人审] 内容: '{content}' | 理由: {result['detection_reason']}")
            pass
        else:
            # print(f"  [正常放行] 内容: '{content}'")
            pass
            
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
