# -*- coding: utf-8 -*-
"""
多智能体基准测试系统 - Web版服务
核心架构：1个中心质检Agent + N个外围攻击Agent
"""

from flask import Flask, jsonify, render_template, request
import random
import time

from config import API_CONFIG
from rule_engine import RULE_ENGINE
from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS, CENTRAL_AGENT, PERIPHERAL_AGENTS,
    GENERATED_USER_PERSONAS, reset_system as reset_agents_system
)
from attack_knowledge_v2 import KNOWLEDGE_STORE

from battle import (
    run_agent_discussion, run_group_strategy_meeting,
    run_adversarial_battle, run_iterative_optimization,
    run_collaborative_attack
)

app = Flask(__name__)

# ============================================================================
# 全局配置
# ============================================================================

# 用户关系图
USER_RELATIONS = []
for i, p1 in enumerate(GENERATED_USER_PERSONAS):
    for p2 in GENERATED_USER_PERSONAS[i+1:]:
        USER_RELATIONS.append({
            "source": p1["id"],
            "target": p2["id"],
            "weight": random.random()
        })

# 社区配置
COMMUNITY_CONFIG = {
    "total_agents": len(GENERATED_USER_PERSONAS),
    "categories": list(set(p.get("group", "其他") for p in GENERATED_USER_PERSONAS)),
    "version": "v2.6.0"
}

# ============================================================================
# API路由
# ============================================================================

@app.get("/")
def index():
    return render_template(
        "index.html",
        personas=GENERATED_USER_PERSONAS,
        relations=USER_RELATIONS,
        provider=API_CONFIG.get("provider", "openai"), # Use openai as default provider
        community_config=COMMUNITY_CONFIG
    )


@app.post("/rules")
def set_rules():
    """设置审核规则"""
    data = request.json or {}
    rules_text = (data.get("rules_text") or "").strip()
    
    # 解析规则
    rules = []
    for i, line in enumerate([l.strip() for l in rules_text.splitlines() if l.strip()]):
        rule_id = f"R{i+1:02d}"
        parts = [p.strip() for p in line.replace("|", " ").split() if p.strip()]
        keywords = []
        for part in parts:
            for token in part.replace("、", ",").split(","):
                token = token.strip()
                if token and token not in keywords:
                    keywords.append(token)
        rules.append({"id": rule_id, "text": line, "keywords": keywords[:5]})
    
    SYSTEM_STATE["rules"] = rules
    SYSTEM_STATE["rules_version"] += 1
    
    # 同步到独立规则引擎
    RULE_ENGINE.set_rules(rules)
    
    # 中心Agent拆解规则（LLM增强，可选）
    CENTRAL_AGENT.refine_rules(rules)
    
    # 将LLM拆解出的变体也同步到规则引擎的自定义词库
    for rule_id, standard in CENTRAL_AGENT.refined_standards.items():
        refined = standard.get("refined", {})
        for variant_type in ["text_variants", "semantic_bypass"]:
            variants_dict = refined.get(variant_type, {})
            if isinstance(variants_dict, dict):
                for vtype, vlist in variants_dict.items():
                    if isinstance(vlist, list):
                        for v in vlist:
                            if v and len(v) >= 2:
                                RULE_ENGINE.add_custom_variants(
                                    standard.get("original_rule", rule_id), [v]
                                )
    
    return jsonify({
        "status": "ok",
        "rules_count": len(rules),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": len(CENTRAL_AGENT.refined_standards)
    })


@app.get("/rules")
def get_rules():
    """获取当前规则"""
    return jsonify({
        "rules": SYSTEM_STATE["rules"],
        "rules_count": len(SYSTEM_STATE["rules"]),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": CENTRAL_AGENT.refined_standards,  # 包含详细拆解
    })


@app.post("/battle/run")
def run_battle():
    """运行单次对抗"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    iteration = data.get("iteration", 0)
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    result = run_adversarial_battle(persona_id, target_keyword, iteration)
    return jsonify(result)


@app.post("/battle/iterate")
def run_iteration():
    """运行迭代优化对抗"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    max_iterations = data.get("max_iterations", 3)
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    result = run_iterative_optimization(persona_id, target_keyword, max_iterations)
    return jsonify(result)


@app.post("/battle/collaborate")
def run_collaboration():
    """运行协作攻击"""
    data = request.json or {}
    agent_ids = data.get("agent_ids", [])
    target_keyword = data.get("target_keyword")
    
    if not agent_ids:
        return jsonify({"error": "缺少agent_ids"}), 400
    
    result = run_collaborative_attack(agent_ids, target_keyword)
    return jsonify(result)


@app.get("/battle/history")
def get_battle_history():
    """获取对抗历史"""
    limit = request.args.get("limit", 50, type=int)
    history = SYSTEM_STATE["battle_history"][-limit:]
    return jsonify({
        "history": history,
        "total_count": len(SYSTEM_STATE["battle_history"]),
    })


@app.get("/inspector/stats")
def get_inspector_stats():
    """获取中心Agent统计"""
    return jsonify({
        "stats": CENTRAL_AGENT.get_stats(),
        "refined_standards_count": len(CENTRAL_AGENT.refined_standards),
    })


@app.get("/agent/<persona_id>/state")
def get_agent_state(persona_id: str):
    """获取外围Agent状态"""
    agent = PERIPHERAL_AGENTS.get(persona_id)
    if not agent:
        return jsonify({"error": "Agent不存在"}), 404
    
    return jsonify(agent.get_state())


@app.post("/agent/<persona_id>/config")
def update_agent_config(persona_id: str):
    """更新Agent配置"""
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return jsonify({"error": "Agent不存在"}), 404
    
    config = request.json
    if not config:
        return jsonify({"error": "无效的配置数据"}), 400
    
    # 更新persona的字段
    updateable_fields = [
        "name", "category", "description", "skill_level", "stealth_rating",
        "behavior_patterns", "background", "core_ability", "attack_strategy",
        "variant_instructions", "chain_of_thought", "output_requirements"
    ]
    
    for field in updateable_fields:
        if field in config:
            persona[field] = config[field]
    
    return jsonify({
        "success": True,
        "message": f"Agent {persona.get('name', persona_id)} 配置已更新",
        "updated_fields": [f for f in updateable_fields if f in config]
    })


@app.get("/agents/states")
def get_all_agent_states():
    """获取所有外围Agent状态"""
    states = []
    for agent_id, agent in PERIPHERAL_AGENTS.items():
        states.append(agent.get_state())
    
    return jsonify({
        "agents": states,
        "total_agents": len(states),
    })


@app.get("/events")
def get_events():
    """获取实时事件流"""
    since = request.args.get("since", 0, type=float)
    count = request.args.get("count", 50, type=int)
    events = EVENT_BUS.get_recent(count, since)
    return jsonify({
        "events": events,
        "count": len(events),
        "latest_timestamp": events[-1]["timestamp"] if events else 0
    })


@app.post("/discussion/start")
def start_discussion():
    """启动Agent间讨论"""
    data = request.json or {}
    topic = data.get("topic", "如何绕过审核")
    agent_ids = data.get("agent_ids", [])
    technique = data.get("technique")
    
    if not agent_ids:
        # 随机选择几个Agent
        agent_ids = random.sample(list(PERSONA_INDEX.keys()), min(3, len(PERSONA_INDEX)))
    
    discussions = run_agent_discussion(agent_ids, topic, technique)
    
    return jsonify({
        "status": "ok",
        "topic": topic,
        "participants": agent_ids,
        "discussions": discussions,
        "total_dialogues": sum(len(d.get("dialogue", [])) for d in discussions)
    })


@app.post("/meeting/start")
def start_meeting():
    """召开反贼策略会议"""
    data = request.json or {}
    topic = data.get("topic", "如何绕过内容审核")
    
    result = run_group_strategy_meeting(topic)
    
    return jsonify(result)


@app.post("/system/reset")
def reset_system():
    """重置系统状态"""
    reset_agents_system()
    RULE_ENGINE.set_rules([])
    return jsonify({"status": "ok", "message": "系统已重置"})


@app.post("/agent/feed")
def feed_agent():
    """投喂资料给Agent"""
    data = request.json or {}
    agent_ids = data.get("agent_ids", [])
    attack_material = data.get("attack_material", "")
    slang_dict = data.get("slang_dict", "")
    bypass_cases = data.get("bypass_cases", "")

    if not any([attack_material, slang_dict, bypass_cases]):
        return jsonify({"error": "投喂内容不能为空"}), 400

    # 如果没有指定agent_ids，则默认投喂给所有agent
    if not agent_ids:
        agent_ids = list(PERIPHERAL_AGENTS.keys())

    for agent_id in agent_ids:
        agent = PERIPHERAL_AGENTS.get(agent_id)
        if agent:
            # 构建学习材料
            learning_material = ""
            if attack_material:
                learning_material += f"## 最新攻击材料\n{attack_material}\n\n"
            if slang_dict:
                learning_material += f"## 最新黑话词典\n{slang_dict}\n\n"
            if bypass_cases:
                learning_material += f"## 最新绕过案例\n{bypass_cases}\n\n"
            
            # 调用Agent的学习方法
            agent.learn_from_external_data(learning_material)

    return jsonify({
        "status": "ok",
        "message": f"已将资料投喂给 {len(agent_ids)} 个Agent",
        "agent_ids": agent_ids
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
