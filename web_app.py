# -*- coding: utf-8 -*-
"""
多智能体基准测试系统 - Web版服务 v3.1.0
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
    run_collaborative_attack, run_collaborative_battle
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
    "version": "v3.1.0"
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
        provider=API_CONFIG.get("provider", "openai"),
        community_config=COMMUNITY_CONFIG,
        audit_mode=SYSTEM_STATE.get("audit_mode", "pre_audit")
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
    
    # 持久化规则到数据库
    from db_manager import save_system_rules
    save_system_rules(rules)
    
    # 同步到独立规则引擎
    RULE_ENGINE.set_rules(rules)
    
    # 中心Agent拆解规则
    CENTRAL_AGENT.refine_rules(rules)
    
    return jsonify({
        "status": "ok",
        "rules_count": len(rules),
        "rules_version": SYSTEM_STATE["rules_version"]
    })


@app.get("/rules")
def get_rules():
    """获取当前规则"""
    return jsonify({
        "rules": SYSTEM_STATE["rules"],
        "rules_count": len(SYSTEM_STATE["rules"]),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": CENTRAL_AGENT.refined_standards,
    })

@app.post("/audit/mode")
def set_audit_mode():
    """设置审核模式"""
    data = request.json or {}
    mode = data.get("mode", "pre_audit")
    if mode in ["pre_audit", "post_audit"]:
        SYSTEM_STATE["audit_mode"] = mode
        return jsonify({"status": "ok", "mode": mode})
    return jsonify({"status": "error", "message": "无效模式"}), 400

@app.post("/battle/run")
def run_battle():
    """运行对抗测试"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    iteration = data.get("iteration", 0)
    battle_type = data.get("type", "single")
    
    if battle_type == "collaborative":
        result = run_collaborative_battle(target_keyword)
    else:
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
    """运行协作攻击 (矩阵模式)"""
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
    from db_manager import load_battle_history
    history = load_battle_history(limit)
    return jsonify({
        "history": history,
        "total_count": len(history),
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
        agent_ids = random.sample(list(PERSONA_INDEX.keys()), min(3, len(PERSONA_INDEX)))
    
    discussions = run_agent_discussion(agent_ids, topic, technique)
    
    return jsonify({
        "status": "ok",
        "topic": topic,
        "participants": agent_ids,
        "discussions": discussions
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

    if not agent_ids:
        agent_ids = list(PERIPHERAL_AGENTS.keys())

    if attack_material:
        KNOWLEDGE_STORE.feed_materials([attack_material])
    if slang_dict:
        slang_list = [line.strip() for line in slang_dict.splitlines() if "=" in line or "→" in line]
        KNOWLEDGE_STORE.feed_slang(slang_list)
    if bypass_cases:
        KNOWLEDGE_STORE.feed_cases([{"bypass": bypass_cases}])

    for agent_id in agent_ids:
        agent = PERIPHERAL_AGENTS.get(agent_id)
        if agent:
            learning_material = ""
            if attack_material: learning_material += f"## 最新攻击材料\n{attack_material}\n\n"
            if slang_dict: learning_material += f"## 最新黑话词典\n{slang_dict}\n\n"
            if bypass_cases: learning_material += f"## 最新绕过案例\n{bypass_cases}\n\n"
            agent.learn_from_external_data(learning_material)

    return jsonify({
        "status": "ok",
        "message": f"已将资料投喂给 {len(agent_ids)} 个Agent",
        "agent_ids": agent_ids
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
