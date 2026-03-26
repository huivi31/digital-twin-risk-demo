# -*- coding: utf-8 -*-
"""
Battle and interaction logic between agents. (v3.1.0 多账号协作版)
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
# 核心对抗逻辑 (v3.1.0 多账号协作)
# ============================================================================

def run_adversarial_battle(persona_id: str, target_keyword: str = None, iteration: int = 0) -> dict:
    """单人对抗测试"""
    agent = PERIPHERAL_AGENTS.get(persona_id)
    if not agent:
        return {"error": "Agent不存在"}

    if not target_keyword:
        target_keyword = "内容安全测试"

    max_retries = 3
    current_retry = 0
    last_fail_reason = None
    retry_history = []

    # 审核模式
    audit_mode = SYSTEM_STATE.get("audit_mode", "pre_audit")

    while current_retry <= max_retries:
        attack_result = agent.craft_attack(target_keyword, iteration=current_retry, last_fail_reason=last_fail_reason)
        content = attack_result["content"]

        # 检测
        defense_result = CENTRAL_INSPECTOR.inspect_content(
            content, technique_used=attack_result["technique_used"], agent_id=persona_id
        )
        
        last_fail_reason = {**defense_result, "content": content}
        
        step_record = {
            "retry_index": current_retry,
            "content": content,
            "detected": defense_result["detected"],
            "hit_layer": defense_result["hit_layer"],
            "reason": defense_result["detection_reason"],
            "audit_mode": audit_mode
        }
        retry_history.append(step_record)

        if not defense_result["detected"]:
            break
        current_retry += 1

    is_success = not defense_result["detected"]
    agent.learn_from_result(is_success, attack_result["technique_used"], detected=defense_result["detected"], hit_layer=defense_result["hit_layer"])

    battle_record = {
        "timestamp": time.time(),
        "persona_id": persona_id,
        "persona_name": agent.persona["name"],
        "target_topic": target_keyword,
        "attack": attack_result,
        "defense": defense_result,
        "is_success": is_success,
        "retries_count": current_retry,
        "retry_history": retry_history,
        "audit_mode": audit_mode
    }
    
    SYSTEM_STATE["battle_history"].append(battle_record)
    if HAS_DB: save_battle(battle_record)
    EVENT_BUS.emit("battle_completed", {"persona_name": agent.persona["name"], "is_success": is_success, "audit_mode": audit_mode})

    return battle_record

def run_collaborative_battle(target_keyword: str, collaborator_count: int = 2) -> dict:
    """多账号协作对抗：主号发帖 + 小号评论"""
    all_agent_ids = list(PERIPHERAL_AGENTS.keys())
    if len(all_agent_ids) < collaborator_count + 1:
        return {"error": "Agent不足"}
    
    participants = random.sample(all_agent_ids, collaborator_count + 1)
    initiator_id = participants[0]
    collaborator_ids = participants[1:]
    
    initiator = PERIPHERAL_AGENTS[initiator_id]
    
    # 1. 主号发帖
    post_result = initiator.craft_collaborative_post(target_keyword)
    post_content = post_result["content"]
    
    # 2. 审核主帖
    post_audit = CENTRAL_INSPECTOR.inspect_content(post_content, technique_used=post_result["technique_used"], agent_id=initiator_id)
    
    comments = []
    collaborator_results = []
    
    # 3. 小号接力评论
    for cid in collaborator_ids:
        collaborator = PERIPHERAL_AGENTS[cid]
        comment_result = collaborator.craft_collaborative_comment(target_keyword, post_content, comments)
        comment_content = comment_result["content"]
        
        # 4. 关联审核（带上下文）
        comment_audit = CENTRAL_INSPECTOR.inspect_content(
            comment_content, 
            technique_used=comment_result["technique_used"], 
            agent_id=cid,
            context=[post_content] + comments
        )
        
        comments.append(comment_content)
        collaborator_results.append({
            "agent_id": cid,
            "agent_name": collaborator.persona["name"],
            "content": comment_content,
            "audit": comment_audit
        })
        
        if comment_audit["detected"]:
            break # 如果被拦截，接力中断
            
    final_success = not any(r["audit"]["detected"] for r in collaborator_results) and not post_audit["detected"]
    
    battle_record = {
        "timestamp": time.time(),
        "type": "collaborative",
        "target_topic": target_keyword,
        "initiator": {"agent_id": initiator_id, "name": initiator.persona["name"], "content": post_content, "audit": post_audit},
        "collaborators": collaborator_results,
        "is_success": final_success
    }
    
    SYSTEM_STATE["battle_history"].append(battle_record)
    EVENT_BUS.emit("collaborative_battle_completed", {"initiator": initiator.persona["name"], "is_success": final_success})
    
    return battle_record
