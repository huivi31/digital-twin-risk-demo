# -*- coding: utf-8 -*-
import json
import random
import time
from battle import run_collaborative_battle, set_hot_event
from agents import PERIPHERAL_AGENTS, SYSTEM_STATE
from rule_engine import RULE_ENGINE

SCENARIOS = {
    "单点攻击-常规场景": ["政治敏感", "暴恐极端"],
    "协作攻击-矩阵模式": ["国家领导人", "黑产引流"]
}

def run_v320_test():
    print("=== v3.2.0 强化防御自检开始 ===")
    
    # 模拟热点事件
    set_hot_event("敏感时期爆发", intensity=2.0)
    
    results = []
    
    # 1. 测试协作攻击 (模拟矩阵号集中发帖)
    print("\n>>> 测试协作攻击-矩阵模式 (行为序列分析)")
    collab_hits = 0
    count = 5
    for i in range(count):
        target = random.choice(SCENARIOS["协作攻击-矩阵模式"])
        result = run_collaborative_battle(target, collaborator_count=4)
        
        # 检查是否被 L0 或 L_Behavior 拦截
        is_blocked = not result.get("is_success")
        if is_blocked:
            collab_hits += 1
            reason = "未知"
            # 找到拦截的那一环
            if result["initiator"]["audit"]["detected"]:
                reason = result["initiator"]["audit"]["hit_layer"]
            else:
                for c in result["collaborators"]:
                    if c["audit"]["detected"]:
                        reason = c["audit"]["hit_layer"]
                        break
            print(f"  [拦截成功] 话题: {target} | 拦截层级: {reason}")
        else:
            print(f"  [绕过成功] 话题: {target}")
            
    results.append({"name": "协作攻击-矩阵模式", "detection_rate": collab_hits/count})
    
    # 2. 测试账号画像风控 (针对高频失败账号)
    print("\n>>> 测试账号画像风控 (L0)")
    # 强制将某个账号设为高风险
    test_agent_id = list(PERIPHERAL_AGENTS.keys())[0]
    RULE_ENGINE.account_profiles[test_agent_id] = {"risk_score": 0.9, "post_count": 10}
    
    from battle import run_adversarial_battle
    res = run_adversarial_battle(test_agent_id, "政治敏感")
    if res["defense"]["detected"] and res["defense"]["hit_layer"] == "L0_Account":
        print(f"  [拦截成功] 高风险账号 {test_agent_id} 被 L0 拦截")
        results.append({"name": "账号画像风控", "status": "PASS"})
    else:
        print(f"  [拦截失败] 高风险账号未被拦截")
        results.append({"name": "账号画像风控", "status": "FAIL"})

    print("\n=== v3.2.0 自检报告总结 ===")
    for r in results:
        print(f"场景: {r['name']} | 结果: {r.get('detection_rate', r.get('status'))}")

if __name__ == "__main__":
    run_v320_test()
