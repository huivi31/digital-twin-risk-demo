# -*- coding: utf-8 -*-
"""
Battle and interaction logic between agents. (v3.4.0 误杀优化版)
"""

import random
import time
import json
from typing import List, Dict, Any

from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    AttackAgent, CENTRAL_INSPECTOR, PERIPHERAL_AGENTS
)
from rule_engine import RULE_ENGINE

try:
    from db_manager import save_battle, load_battle_history
    HAS_DB = True
except ImportError:
    HAS_DB = False

def run_adversarial_battle(persona_id: str, target_keyword: str = None, iteration: int = 0) -> dict:
    """单人对抗测试 (v3.4.0 支持重试与待人审)"""
    agent = PERIPHERAL_AGENTS.get(persona_id)
    if not agent: return {"error": "Agent不存在"}

    if not target_keyword: target_keyword = "内容安全测试"

    max_retries = 3
    current_retry = 0
    last_fail_reason = None
    retry_history = []
    
    final_defense_result = None

    while current_retry <= max_retries:
        attack_result = agent.craft_attack(target_keyword, iteration=current_retry, last_fail_reason=last_fail_reason)
        content = attack_result["content"]

        defense_result = CENTRAL_INSPECTOR.inspect_content(
            content, technique_used=attack_result["technique_used"], agent_id=persona_id
        )
        
        final_defense_result = defense_result
        is_detected = defense_result["detected"]
        is_pending = defense_result.get("is_pending", False)
        
        retry_history.append({
            "retry_index": current_retry, "content": content, 
            "detected": is_detected, "is_pending": is_pending,
            "hit_layer": defense_result["hit_layer"], "reason": defense_result["reason"]
        })

        # 判定逻辑：
        # 1. 如果没被拦截 (not is_detected)，直接绕过成功
        # 2. 如果被拦截但属于“待人审” (is_pending)，则停止重试，视为“阻断发布但待审”
        # 3. 如果被直接拦截且非待审，则进入重试链路
        
        if not is_detected:
            break
        elif is_pending:
            break
        else:
            last_fail_reason = {**defense_result, "content": content}
            current_retry += 1

    is_success = not final_defense_result["detected"]
    is_pending = final_defense_result.get("is_pending", False)
    
    agent.learn_from_result(
        is_success, attack_result["technique_used"], 
        detected=final_defense_result["detected"], hit_layer=final_defense_result["hit_layer"]
    )
    
    # 更新账号画像风险分 (仅针对直接拦截的内容增加风险分)
    if final_defense_result["detected"] and not is_pending:
        profile = RULE_ENGINE.account_profiles.get(persona_id, {"risk_score": 0.0, "post_count": 0})
        profile["risk_score"] = min(1.0, profile["risk_score"] + 0.1)
        profile["post_count"] += 1
        RULE_ENGINE.account_profiles[persona_id] = profile

    battle_record = {
        "timestamp": time.time(),
        "persona_id": persona_id,
        "persona_name": agent.persona["name"],
        "target_topic": target_keyword,
        "attack": attack_result,
        "defense": final_defense_result,
        "is_success": is_success,
        "is_pending": is_pending,
        "retries_count": current_retry,
        "retry_history": retry_history
    }
    
    SYSTEM_STATE["battle_history"].append(battle_record)
    if HAS_DB: save_battle(battle_record)
    return battle_record

def run_collaborative_battle(target_keyword: str, collaborator_count: int = 4) -> dict:
    """强化版多账号协作对抗 (v3.4.0)"""
    all_agent_ids = list(PERIPHERAL_AGENTS.keys())
    participants = random.sample(all_agent_ids, collaborator_count + 1)
    initiator_id = participants[0]
    collaborator_ids = participants[1:]
    
    # 1. 主号发帖
    initiator = PERIPHERAL_AGENTS[initiator_id]
    post_result = initiator.craft_collaborative_post(target_keyword)
    post_content = post_result["content"]
    post_audit = CENTRAL_INSPECTOR.inspect_content(post_content, technique_used="协作-主帖", agent_id=initiator_id)
    
    comments = []
    collaborator_results = []
    
    # 2. 小号密集接力
    for cid in collaborator_ids:
        collaborator = PERIPHERAL_AGENTS[cid]
        comment_result = collaborator.craft_collaborative_comment(target_keyword, post_content, comments)
        comment_content = comment_result["content"]
        
        # 关联分析检测 (带上下文)
        comment_audit = CENTRAL_INSPECTOR.inspect_content(
            comment_content, technique_used="协作-评论", agent_id=cid, context=[post_content] + comments
        )
        
        comments.append(comment_content)
        collaborator_results.append({"agent_id": cid, "name": collaborator.persona["name"], "content": comment_content, "audit": comment_audit})
        
        # 如果命中拦截且非待审，直接阻断
        if comment_audit["detected"] and not comment_audit.get("is_pending", False): break
            
    final_success = not any(r["audit"]["detected"] for r in collaborator_results) and not post_audit["detected"]
    
    battle_record = {
        "timestamp": time.time(),
        "type": "collaborative",
        "target_topic": target_keyword,
        "initiator": {"agent_id": initiator_id, "name": initiator.persona["name"], "content": post_content, "audit": post_audit},
        "collaborators": collaborator_results,
        "is_success": final_success,
        "is_pending": any(r["audit"].get("is_pending", False) for r in collaborator_results) or post_audit.get("is_pending", False)
    }
    SYSTEM_STATE["battle_history"].append(battle_record)
    return battle_record

def set_hot_event(name: str, intensity: float = 1.0):
    """设置热点事件模拟"""
    SYSTEM_STATE["hot_event"] = {"name": name, "peak_time": time.time(), "intensity": intensity}
    EVENT_BUS.emit("hot_event_started", SYSTEM_STATE["hot_event"])
