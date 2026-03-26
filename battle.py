# -*- coding: utf-8 -*-
"""
Battle and interaction logic between agents. (v3.0.0 重试链路版)
"""

import random
import time
import json

from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    AttackAgent, CENTRAL_INSPECTOR, PERIPHERAL_AGENTS
)

try:
    from db_manager import save_battle, load_battle_history
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ============================================================================
# Multi-Agent 讨论系统
# ============================================================================

def run_agent_discussion(agent_ids: list, topic: str, successful_technique: str = None) -> list:
    discussions = []
    if len(agent_ids) < 2:
        return discussions
    participants = random.sample(agent_ids, min(3, len(agent_ids)))
    initiator_id = participants[0]
    initiator_persona = PERSONA_INDEX.get(initiator_id)
    if not initiator_persona:
        return discussions
    initiator_agent = AttackAgent(initiator_persona)
    EVENT_BUS.emit("discussion_start", {"participants": [PERSONA_INDEX.get(pid, {}).get("name", pid) for pid in participants], "topic": topic})
    for i in range(1, len(participants)):
        peer_id = participants[i]
        peer_persona = PERSONA_INDEX.get(peer_id)
        if not peer_persona: continue
        peer_name = peer_persona.get("name", peer_id)
        peer_technique = successful_technique or "通用技巧"
        discussion_result = {"speaker": initiator_agent.persona["name"], "content": f"我觉得{peer_technique}手法不错。"}
        discussions.append(discussion_result)
    EVENT_BUS.emit("discussion_end", {"total": len(discussions)})
    return discussions

def run_group_strategy_meeting(topic: str) -> dict:
    participants = random.sample(list(PERSONA_INDEX.keys()), min(5, len(PERSONA_INDEX)))
    meeting_log = []
    for pid in participants:
        persona = PERSONA_INDEX.get(pid)
        agent = AttackAgent(persona)
        content = agent._call_llm(f"你是{persona['name']}，对如何绕过关于'{topic}'的审核发表见解。")
        speech = {"speaker": persona["name"], "content": content}
        meeting_log.append(speech)
        EVENT_BUS.emit("meeting_speech", speech)
    return {"topic": topic, "log": meeting_log}

# ============================================================================
# 核心对抗逻辑 (v3.0.0 重试链路)
# ============================================================================

def run_adversarial_battle(persona_id: str, target_keyword: str = None, iteration: int = 0) -> dict:
    """运行对抗测试（支持重试链路 v3.0.0）"""
    agent = PERIPHERAL_AGENTS.get(persona_id)
    if not agent:
        return {"error": "Agent不存在"}

    if not target_keyword:
        target_keyword = "内容安全测试"

    max_retries = 3
    current_retry = 0
    last_fail_reason = None
    retry_history = []

    while current_retry <= max_retries:
        # 1. 攻击侧：生成攻击
        attack_result = agent.craft_attack(target_keyword, iteration=current_retry, last_fail_reason=last_fail_reason)
        content = attack_result["content"]

        # 2. 防御侧：检测
        defense_result = CENTRAL_INSPECTOR.inspect_content(
            content, technique_used=attack_result["technique_used"], agent_id=persona_id
        )
        
        last_fail_reason = {**defense_result, "content": content}
        
        step_record = {
            "retry_index": current_retry,
            "content": content,
            "detected": defense_result["detected"],
            "hit_layer": defense_result["hit_layer"],
            "reason": defense_result["detection_reason"]
        }
        retry_history.append(step_record)

        if not defense_result["detected"]:
            break
        current_retry += 1

    # 3. 最终结果
    is_success = not defense_result["detected"]
    agent.learn_from_result(
        is_success, attack_result["technique_used"],
        detected=defense_result["detected"],
        hit_layer=defense_result["hit_layer"],
        hit_layer_num=defense_result["hit_layer_num"]
    )

    battle_record = {
        "timestamp": time.time(),
        "persona_id": persona_id,
        "persona_name": agent.persona["name"],
        "target_topic": target_keyword,
        "attack": attack_result,
        "defense": defense_result,
        "is_success": is_success,
        "iteration": iteration,
        "retries_count": current_retry,
        "retry_history": retry_history,
        "result": {"bypass_success": is_success}
    }
    
    SYSTEM_STATE["battle_history"].append(battle_record)
    if HAS_DB:
        save_battle(battle_record)
        
    EVENT_BUS.emit("battle_completed", {
        "persona_name": agent.persona["name"],
        "is_success": is_success,
        "hit_layer": defense_result["hit_layer"],
        "retries": current_retry
    })

    return battle_record

def run_iterative_optimization(persona_id: str, target_keyword: str, max_iterations: int = 3) -> dict:
    results = []
    for i in range(max_iterations):
        res = run_adversarial_battle(persona_id, target_keyword, iteration=i)
        results.append(res)
        if res["is_success"]: break
    return {"results": results, "final_success": results[-1]["is_success"]}

def run_collaborative_attack(agent_ids: list, target_keyword: str) -> dict:
    results = [run_adversarial_battle(aid, target_keyword) for aid in agent_ids]
    return {"results": results, "success_rate": sum(1 for r in results if r["is_success"])/len(results)}
