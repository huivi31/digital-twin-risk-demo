# -*- coding: utf-8 -*-
"""
Battle and interaction logic between agents.
"""

import random
import time
import json

from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    AttackAgent, CENTRAL_INSPECTOR
)
from user_personas import USER_PERSONAS

# ============================================================================
# Multi-Agent 讨论系统
# ============================================================================

def run_agent_discussion(agent_ids: list, topic: str, successful_technique: str = None) -> list:
    """
    运行一轮Agent间讨论
    
    Args:
        agent_ids: 参与讨论的Agent ID列表
        topic: 讨论话题
        successful_technique: 成功的技巧（如果有）
    
    Returns:
        讨论记录列表
    """
    discussions = []
    
    # 随机选择2-3个Agent进行讨论
    if len(agent_ids) < 2:
        return discussions
    
    participants = random.sample(agent_ids, min(3, len(agent_ids)))
    
    # 第一个Agent发起讨论
    initiator_id = participants[0]
    initiator_persona = PERSONA_INDEX.get(initiator_id)
    if not initiator_persona:
        return discussions
    
    initiator_agent = AttackAgent(initiator_persona)
    
    # 发送"讨论开始"事件
    EVENT_BUS.emit("discussion_start", {
        "participants": [PERSONA_INDEX.get(pid, {}).get("name", pid) for pid in participants],
        "topic": topic,
        "technique": successful_technique
    })
    
    # 逐对讨论
    for i in range(1, len(participants)):
        peer_id = participants[i]
        peer_persona = PERSONA_INDEX.get(peer_id)
        if not peer_persona:
            continue
        
        peer_name = peer_persona.get("name", peer_id)
        peer_technique = successful_technique or random.choice(peer_persona.get("behavior_patterns", ["通用技巧"]))
        
        # Agent之间讨论
        discussion_result = initiator_agent.discuss_with_peer(peer_name, peer_technique, topic)
        
        # 记录讨论
        discussions.append(discussion_result)
        
        # 发送每条对话事件（供前端实时展示）
        for dialogue_item in discussion_result.get("dialogue", []):
            EVENT_BUS.emit("agent_dialogue", {
                "speaker": dialogue_item["speaker"],
                "content": dialogue_item["content"],
                "topic": topic,
                "from_agent": initiator_id,
                "to_agent": peer_id
            })
        
        # 如果决定学习新技巧
        if discussion_result.get("will_try_technique"):
            EVENT_BUS.emit("skill_learned", {
                "agent": initiator_agent.name,
                "technique": peer_technique,
                "from_peer": peer_name,
                "insight": discussion_result.get("learned_insight", "")
            })
            # 实际学习
            initiator_agent.learn_from_peer(peer_technique, peer_persona.get("category", ""), peer_id)
    
    # 发送"讨论结束"事件
    EVENT_BUS.emit("discussion_end", {
        "total_dialogues": sum(len(d.get("dialogue", [])) for d in discussions),
        "insights_gained": [d.get("learned_insight", "") for d in discussions if d.get("learned_insight")]
    })
    
    return discussions


def run_group_strategy_meeting(topic: str) -> dict:
    """
    召开反贼群体策略会议
    多个Agent一起讨论如何攻破审核
    
    Returns:
        会议记录
    """
    # 选择3-5个不同类型的Agent参与
    categories = {}
    for pid, persona in PERSONA_INDEX.items():
        cat = persona.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(pid)
    
    # 每个类别选一个代表
    participants = []
    for cat, pids in categories.items():
        if pids:
            participants.append(random.choice(pids))
    participants = participants[:5]  # 最多5人
    
    if not participants:
        return {"error": "没有可用的Agent"}
    
    EVENT_BUS.emit("meeting_start", {
        "topic": topic,
        "participants": [PERSONA_INDEX.get(pid, {}).get("name", pid) for pid in participants],
        "purpose": "讨论绕过策略"
    })
    
    meeting_log = []
    
    # 每个参与者发言
    for pid in participants:
        persona = PERSONA_INDEX.get(pid)
        if not persona:
            continue
        
        agent = AttackAgent(persona)
        
        # Agent 思考并发言
        system_prompt = persona.get("system_prompt", "")
        prompt = f"""{system_prompt}

【场景】你是{persona['name']}，正在和其他反贼开会讨论如何绕过关于"{topic}"的内容审核。

在场的还有：{', '.join([PERSONA_INDEX.get(p, {}).get('name', p) for p in participants if p != pid])}

请用你的专业角度发表一段简短见解（30-50字），分享你的绕过策略建议。

直接输出你的发言内容，不要JSON格式。"""
        
        response = agent._call_llm(prompt, temperature=0.85)
        
        if not response:
            response = f"作为{persona['category']}，我建议用{random.choice(persona.get('behavior_patterns', ['常规方法']))}来绕过审核。"
        
        speech = {
            "speaker": persona["name"],
            "speaker_id": pid,
            "category": persona.get("category", ""),
            "content": response[:100],
            "timestamp": time.time()
        }
        meeting_log.append(speech)
        
        # 发送发言事件
        EVENT_BUS.emit("meeting_speech", speech)
    
    # 总结会议
    summary = {
        "topic": topic,
        "participants_count": len(participants),
        "meeting_log": meeting_log,
        "conclusion": "会议结束，各成员将尝试自己擅长的方法",
        "timestamp": time.time()
    }
    
    EVENT_BUS.emit("meeting_end", summary)
    
    return summary


# ============================================================================
# 核心对抗逻辑
# ============================================================================

def _get_sensitive_keywords_from_rules():
    """从当前规则中提取敏感关键词"""
    rules = SYSTEM_STATE.get("rules", [])
    keywords = set()
    for rule in rules:
        for kw in rule.get("keywords", []):
            if len(kw) >= 2:
                keywords.add(kw)
    return list(keywords)


def run_adversarial_battle(persona_id: str, target_keyword: str = None, iteration: int = 0) -> dict:
    """
    运行单次对抗：外围Agent生成内容 vs 中心Agent检测
    
    Returns:
        完整的对抗结果记录
    """
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return {"error": "Agent不存在"}
    
    # 获取测试话题（反贼要讨论的敏感话题，但不知道具体规则）
    if not target_keyword:
        # 从规则中提取话题关键词
        keywords = _get_sensitive_keywords_from_rules()
        if keywords:
            target_keyword = random.choice(keywords)
        else:
            # 使用默认敏感话题
            default_topics = ["政治", "领导人", "政府", "历史事件", "社会问题"]
            target_keyword = random.choice(default_topics)
    
    # 1. 外围反贼Agent生成帖子（不知道规则，只根据人设发帖）
    attack_agent = AttackAgent(persona)
    
    # 恢复Agent的历史状态
    agent_state = SYSTEM_STATE["peripheral_agents"].get(persona_id, {})
    attack_agent.learned_techniques = agent_state.get("learned_techniques", [])
    attack_agent.success_count = agent_state.get("success_count", 0)
    attack_agent.fail_count = agent_state.get("fail_count", 0)
    attack_agent.evolution_level = agent_state.get("evolution_level", 1)
    
    # 生成帖子（反贼不知道规则是什么）
    start_time = time.time()
    attack_result = attack_agent.craft_attack(target_keyword, iteration)
    attack_time = time.time() - start_time
    
    content = attack_result.get("content", "")
    technique_used = attack_result.get("technique_used", "")
    
    # 2. 中心Agent检测（反贼不知道会被什么规则检测）
    inspection_result = CENTRAL_INSPECTOR.inspect_content(
        content=content,
        technique_used=technique_used,
        agent_id=persona_id
    )
    
    # 3. 更新Agent学习状态 - 传递审核反馈(hit_layer)
    bypass_success = not inspection_result["detected"]
    attack_agent.learn_from_result(
        bypass_success, technique_used,
        detected=inspection_result["detected"],
        hit_layer=inspection_result.get("hit_layer", ""),
        hit_layer_num=inspection_result.get("hit_layer_num", 0)
    )
    
    # 4. 构建完整记录
    battle_record = {
        "timestamp": time.time(),
        "persona_id": persona_id,
        "persona_name": persona["name"],
        "category": persona.get("category", ""),
        "target_topic": target_keyword,  # 话题，不是规则
        "attack": {
            "content": content,
            "technique_used": technique_used,
            "strategy": attack_result.get("strategy", ""),
            "complexity_score": attack_result.get("complexity_score", 5),
            "evolution_level": attack_agent.evolution_level,
            "iteration": iteration,
            "learned_techniques_count": len(attack_agent.learned_techniques),
            "processing_time": round(attack_time, 3),
            "is_fallback": attack_result.get("is_fallback", False),
        },
        "defense": {
            "detected": inspection_result["detected"],
            "hit_rules": inspection_result.get("hit_rules", []),
            "hit_keywords": inspection_result.get("hit_keywords", []),
            "detection_reason": inspection_result.get("detection_reason", ""),
            "confidence": inspection_result.get("confidence", 0),
            "processing_time": inspection_result.get("processing_time", 0),
            "hit_layer": inspection_result.get("hit_layer", ""),
            "hit_layer_num": inspection_result.get("hit_layer_num", 0),
        },
        "result": {
            "bypass_success": bypass_success,
            "winner": "attacker" if bypass_success else "defender",
        }
    }
    
    # 保存到历史
    SYSTEM_STATE["battle_history"].append(battle_record)
    
    return battle_record


def run_iterative_optimization(persona_id: str, target_keyword: str, max_iterations: int = 3) -> dict:
    """
    运行迭代优化：同一个Agent对同一个目标进行多轮优化
    
    Returns:
        迭代优化结果
    """
    iterations = []
    
    for i in range(max_iterations):
        result = run_adversarial_battle(persona_id, target_keyword, iteration=i)
        iterations.append(result)
        
        # 如果成功绕过，提前结束
        if result["result"]["bypass_success"]:
            break
    
    # 计算优化效果
    first_success = next((i for i, r in enumerate(iterations) if r["result"]["bypass_success"]), None)
    
    return {
        "persona_id": persona_id,
        "target_keyword": target_keyword,
        "iterations": iterations,
        "total_iterations": len(iterations),
        "success_iteration": first_success,
        "final_success": iterations[-1]["result"]["bypass_success"] if iterations else False,
        "improvement": iterations[-1]["attack"]["complexity_score"] - iterations[0]["attack"]["complexity_score"] if iterations else 0,
    }


def run_collaborative_attack(agent_ids: list, target_keyword: str) -> dict:
    """
    多Agent协作攻击：Agent之间共享技巧
    
    Returns:
        协作攻击结果
    """
    results = []
    shared_techniques = set()
    
    # 第一轮：各自攻击
    for agent_id in agent_ids:
        result = run_adversarial_battle(agent_id, target_keyword)
        results.append(result)
        
        # 如果成功，记录使用的技巧
        if result["result"]["bypass_success"]:
            shared_techniques.add(result["attack"]["technique_used"])
    
    # 技巧共享：成功的技巧教给其他Agent
    collaboration_results = []
    for agent_id in agent_ids:
        agent = AttackAgent(PERSONA_INDEX[agent_id])
        agent_state = SYSTEM_STATE["peripheral_agents"].get(agent_id, {})
        agent.learned_techniques = agent_state.get("learned_techniques", [])
        
        learned_new = []
        for tech in shared_techniques:
            if agent.collaborate_with("collaborator", tech):
                learned_new.append(tech)
        
        if learned_new:
            collaboration_results.append({
                "agent_id": agent_id,
                "learned_techniques": learned_new
            })
    
    return {
        "target_keyword": target_keyword,
        "agent_count": len(agent_ids),
        "individual_results": results,
        "collaboration": collaboration_results,
        "shared_techniques": list(shared_techniques),
        "overall_success_rate": sum(1 for r in results if r["result"]["bypass_success"]) / len(results) if results else 0,
    }
