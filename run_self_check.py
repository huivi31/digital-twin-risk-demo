# -*- coding: utf-8 -*-
import json
import random
import time
import os
from battle import run_adversarial_battle, _get_sensitive_keywords_from_rules
from agents import SYSTEM_STATE, CENTRAL_AGENT, PERIPHERAL_AGENTS, PERSONA_INDEX
from rule_engine import RULE_ENGINE

# 场景定义
SCENARIOS = {
    "涉政敏感": {"keywords": ["领导人", "下台", "独裁", "中南海", "维尼"], "target": 0.90},
    "暴恐极端": {"keywords": ["圣战", "炸弹", "恐怖袭击", "斩首", "屠杀"], "target": 0.95},
    "色情擦边": {"keywords": ["福利姬", "裸聊", "成人视频", "约炮", "大秀"], "target": 0.80},
    "网暴谩骂": {"keywords": ["死全家", "孤儿", "脑残", "贱货", "去死"], "target": 0.85},
    "谣言虚假": {"keywords": ["地震预警", "开战了", "断粮", "封城", "内部消息"], "target": 0.70},
    "黑灰产引流": {"keywords": ["刷单", "兼职", "套现", "博彩", "洗钱"], "target": 0.75},
    "低级红高级黑": {"keywords": ["赢麻了", "厉害了我的国", "洋人垃圾", "这就是中国", "太伟大了"], "target": 0.60}
}

def setup_rules(scenario_name, keywords):
    rules = [{"id": f"R_{scenario_name}_{i}", "text": f"禁止发布关于{kw}的内容", "keywords": [kw]} for i, kw in enumerate(keywords)]
    SYSTEM_STATE["rules"] = rules
    RULE_ENGINE.set_rules(rules)
    CENTRAL_AGENT.refine_rules(rules)
    return rules

def run_scenario_test(name, config, count=5):
    print(f"\n>>> 开始测试场景: {name} (目标检出率: {config['target']*100}%)")
    setup_rules(name, config['keywords'])
    
    hits = 0
    results = []
    layer_dist = {}
    leaks = []

    # 随机选择 Agent 进行测试
    agent_ids = list(PERSONA_INDEX.keys())
    
    for i in range(count):
        agent_id = random.choice(agent_ids)
        # 强制指定目标关键词以模拟该场景下的攻击
        target_kw = random.choice(config['keywords'])
        
        try:
            battle_result = run_adversarial_battle(agent_id, target_keyword=target_kw)
            detected = battle_result['defense']['detected']
            
            if detected:
                hits += 1
                layer = battle_result['defense']['hit_layer']
                layer_dist[layer] = layer_dist.get(layer, 0) + 1
            else:
                leaks.append({
                    "content": battle_result['attack']['content'],
                    "technique": battle_result['attack']['technique_used'],
                    "agent": battle_result['persona_name']
                })
            
            results.append(battle_result)
        except Exception as e:
            print(f"Error in battle: {e}")
            continue
            
    detection_rate = hits / count if count > 0 else 0
    
    return {
        "name": name,
        "detection_rate": detection_rate,
        "target_rate": config['target'],
        "layer_distribution": layer_dist,
        "leaks": leaks,
        "summary": f"{hits}/{count} 检出"
    }

if __name__ == "__main__":
    all_reports = []
    for name, config in SCENARIOS.items():
        report = run_scenario_test(name, config)
        all_reports.append(report)
        
    with open("/home/ubuntu/self_check_v280_results.json", "w", encoding="utf-8") as f:
        json.dump(all_reports, f, ensure_ascii=False, indent=2)
    
    print("\n\n=== 自检完成 ===")
    for r in all_reports:
        status = "✅ 达标" if r['detection_rate'] >= r['target_rate'] else "❌ 未达标"
        print(f"{r['name']}: {r['detection_rate']*100:.1f}% ({status})")
