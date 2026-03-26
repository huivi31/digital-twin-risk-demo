# -*- coding: utf-8 -*-
"""
多智能体基准测试系统 - Web版服务 v3.4.0 (误杀优化版)
"""

from flask import Flask, jsonify, render_template, request
import random
import time
import json

from config import API_CONFIG
from rule_engine import RULE_ENGINE
from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS, CENTRAL_AGENT, PERIPHERAL_AGENTS,
    GENERATED_USER_PERSONAS
)
from attack_knowledge_v2 import KNOWLEDGE_STORE
from battle import run_adversarial_battle, run_collaborative_battle

app = Flask(__name__)
VERSION = "v3.4.0"

@app.get("/")
def index():
    return render_template(
        "index.html",
        personas=GENERATED_USER_PERSONAS,
        version=VERSION,
        audit_mode=SYSTEM_STATE.get("audit_mode", "pre_audit")
    )

@app.post("/rules")
def set_rules():
    """设置审核规则"""
    data = request.json or {}
    rules_text = (data.get("rules_text") or "").strip()
    rules = []
    for i, line in enumerate([l.strip() for l in rules_text.splitlines() if l.strip()]):
        rule_id = f"R{i+1:02d}"
        parts = [p.strip() for p in line.replace("|", " ").split() if p.strip()]
        keywords = []
        for part in parts:
            for token in part.replace("、", ",").split(","):
                token = token.strip()
                if token and token not in keywords: keywords.append(token)
        rules.append({"id": rule_id, "text": line, "keywords": keywords[:5]})
    
    SYSTEM_STATE["rules"] = rules
    SYSTEM_STATE["rules_version"] += 1
    RULE_ENGINE.set_rules(rules)
    CENTRAL_AGENT.refine_rules(rules)
    
    return jsonify({"status": "ok", "rules_count": len(rules), "rules_version": SYSTEM_STATE["rules_version"]})

@app.post("/battle/run")
def run_battle():
    """运行对抗测试 (v3.4.0)"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    battle_type = data.get("type", "single")
    
    if battle_type == "collaborative":
        result = run_collaborative_battle(target_keyword)
    else:
        if not persona_id: return jsonify({"error": "缺少persona_id"}), 400
        result = run_adversarial_battle(persona_id, target_keyword)
    
    return jsonify(result)

@app.get("/battle/history")
def get_battle_history():
    """获取对抗历史"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"history": SYSTEM_STATE["battle_history"][-limit:]})

@app.get("/agents/states")
def get_all_agent_states():
    """获取所有外围Agent状态"""
    states = [agent.get_state() for agent in PERIPHERAL_AGENTS.values()]
    return jsonify({"agents": states, "system_state": SYSTEM_STATE})

@app.post("/audit/mode")
def set_audit_mode():
    """设置审核模式"""
    mode = request.json.get("mode")
    if mode in ["pre_audit", "post_audit"]:
        SYSTEM_STATE["audit_mode"] = mode
        return jsonify({"status": "ok", "mode": mode})
    return jsonify({"status": "error"}), 400

@app.post("/platform/set")
def set_platform():
    """设置平台环境"""
    platform = request.json.get("platform")
    if platform in ["weibo", "douyin", "xiaohongshu", "bilibili"]:
        SYSTEM_STATE["platform"] = platform
        return jsonify({"status": "ok", "platform": platform})
    return jsonify({"status": "error"}), 400

@app.post("/agent/feed")
def feed_agent():
    """投喂资料"""
    data = request.json or {}
    attack_material = data.get("attack_material", "")
    slang_dict = data.get("slang_dict", "")
    bypass_cases = data.get("bypass_cases", "")

    if attack_material: KNOWLEDGE_STORE.feed_materials([attack_material])
    if slang_dict: KNOWLEDGE_STORE.feed_slang(slang_dict.splitlines())
    if bypass_cases: KNOWLEDGE_STORE.feed_cases([{"bypass": bypass_cases}])

    return jsonify({"status": "ok", "message": "资料已投喂"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
