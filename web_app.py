# -*- coding: utf-8 -*-
"""
多智能体基准测试系统 - Web版服务
核心架构：1个中心质检Agent + N个外围攻击Agent
"""

from flask import Flask, jsonify, render_template, request
import random
import time

from config import API_CONFIG
from user_personas import USER_PERSONAS, USER_RELATIONS, COMMUNITY_CONFIG
from rule_engine import RULE_ENGINE
from attack_knowledge import KNOWLEDGE_STORE

# Import from new modules
from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    CentralInspectorAgent, AttackAgent, CENTRAL_INSPECTOR
)
from battle import (
    run_agent_discussion, run_group_strategy_meeting,
    run_adversarial_battle, run_iterative_optimization,
    run_collaborative_attack
)

app = Flask(__name__)

# ============================================================================
# API路由
# ============================================================================

@app.get("/")
def index():
    return render_template(
        "index.html",
        personas=USER_PERSONAS,
        relations=USER_RELATIONS,
        provider=API_CONFIG.get("provider", "gemini"),
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
    CENTRAL_INSPECTOR.refine_rules(rules)
    
    # 将LLM拆解出的变体也同步到规则引擎的自定义词库
    for rule_id, standard in CENTRAL_INSPECTOR.refined_standards.items():
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
        "refined_standards": len(CENTRAL_INSPECTOR.refined_standards)
    })


@app.get("/rules")
def get_rules():
    """获取当前规则"""
    return jsonify({
        "rules": SYSTEM_STATE["rules"],
        "rules_count": len(SYSTEM_STATE["rules"]),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": CENTRAL_INSPECTOR.refined_standards,  # 包含详细拆解
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
        "stats": CENTRAL_INSPECTOR.get_stats(),
        "refined_standards_count": len(CENTRAL_INSPECTOR.refined_standards),
    })


@app.get("/agent/<persona_id>/state")
def get_agent_state(persona_id: str):
    """获取外围Agent状态"""
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return jsonify({"error": "Agent不存在"}), 404
    
    agent = AttackAgent(persona)
    agent_state = SYSTEM_STATE["peripheral_agents"].get(persona_id, {})
    agent.learned_techniques = agent_state.get("learned_techniques", [])
    agent.success_count = agent_state.get("success_count", 0)
    agent.fail_count = agent_state.get("fail_count", 0)
    agent.evolution_level = agent_state.get("evolution_level", 1)
    
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
    
    # 同时更新USER_PERSONAS中的数据
    for i, p in enumerate(USER_PERSONAS):
        if p["id"] == persona_id:
            USER_PERSONAS[i] = persona
            break
    
    return jsonify({
        "success": True,
        "message": f"Agent {persona.get('name', persona_id)} 配置已更新",
        "updated_fields": [f for f in updateable_fields if f in config]
    })


@app.get("/agents/states")
def get_all_agent_states():
    """获取所有外围Agent状态"""
    states = []
    for persona in USER_PERSONAS:
        agent = AttackAgent(persona)
        agent_state = SYSTEM_STATE["peripheral_agents"].get(persona["id"], {})
        agent.learned_techniques = agent_state.get("learned_techniques", [])
        agent.success_count = agent_state.get("success_count", 0)
        agent.fail_count = agent_state.get("fail_count", 0)
        agent.evolution_level = agent_state.get("evolution_level", 1)
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
    # Reset system state in agents module
    SYSTEM_STATE["central_agent"]["detection_rules"] = []
    SYSTEM_STATE["central_agent"]["refined_standards"] = {}
    SYSTEM_STATE["central_agent"]["detection_stats"] = {
        "total_checked": 0,
        "total_detected": 0,
        "total_bypassed": 0,
        "by_technique": {},
        "by_keyword": {},
    }
    SYSTEM_STATE["peripheral_agents"] = {
        p["id"]: {
            "persona": p,
            "learned_techniques": [],
            "success_count": 0,
            "fail_count": 0,
            "evolution_level": 1,
            "last_strategy": None,
        } for p in USER_PERSONAS
    }
    SYSTEM_STATE["battle_history"] = []
    SYSTEM_STATE["rules"] = []
    SYSTEM_STATE["rules_version"] = 0
    
    CENTRAL_INSPECTOR.reset_stats()
    CENTRAL_INSPECTOR.detection_rules = []
    CENTRAL_INSPECTOR.refined_standards = {}
    RULE_ENGINE.reset_stats()
    RULE_ENGINE.set_rules([])
    RULE_ENGINE.custom_variants = {}
    KNOWLEDGE_STORE.dlear()
    
    return jsonify({"status": "reset", "message": "系统已重置"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


# ============================================================================
# 知识投喂 API
# ============================================================================

@app.post("/knowledge/feed")
def feed_knowledge():
    """投喂攻击资料给所有Agent学习"""
    data = request.json or {}
    feed_type = data.get("type", "materials")  # materials / slang / cases
    content = data.get("content", "")
    items = data.get("items", [])
    
    result = {"fed_count": 0, "type": feed_type}
    
    if feed_type == "materials":
        # 文本资料：每行一条
        if content:
            texts = [line.strip() for line in content.splitlines() if line.strip()]
        else:
            texts = items
        count = KNOWLEDGE_STORE.feed_materials(texts, data.get("category", "通用"))
        result["fed_count"] = count
    
    elif feed_type == "slang":
        # 行业黑话："词=含义" 格式，每行一条
        if content:
            entries = [line.strip() for line in content.splitlines() if line.strip()]
        else:
            entries = items
        count = KNOWLEDGE_STORE.feed_slang(entries)
        result["fed_count"] = count
        
        # 黑话同时加入规则引擎的自定义变体
        for entry in entries:
            if isinstance(entry, str) and ("=" in entry or "→" in entry):
                sep = "=" if "=" in entry else "→"
                parts = entry.split(sep, 1)
                if len(parts) == 2:
                    RULE_ENGINE.add_custom_variants(parts[1].strip(), [parts[0].strip()])
    
    elif feed_type == "cases":
        # 绕过案例
        if isinstance(items, list):
            count = KNOWLEDGE_STORE.feed_cases(items)
            result["fed_count"] = count
    
    # 发送事件
    EVENT_BUS.emit("knowledge_fed", {
        "type": feed_type,
        "count": result["fed_count"],
        "message": f"投喂了{result['fed_count']}条{feed_type}资料"
    })
    
    result["knowledge_version"] = KNOWLEDGE_STORE.version
    result["summary"] = KNOWLEDGE_STORE.get_summary()
    return jsonify(result)


@app.get("/knowledge/list")
def list_knowledge():
    """查看已投喂资料"""
    return jsonify(KNOWLEDGE_STORE.get_summary())


@app.post("/knowledge/clear")
def clear_knowledge():
    """清空投喂资料"""
    KNOWLEDGE_STORE.clear()
    return jsonify({"status": "cleared", "message": "投喂资料已清空"})


@app.get("/rule-engine/stats")
def get_rule_engine_stats():
    """获取规则引擎统计（按层统计）"""
    return jsonify(RULE_ENGINE.get_stats())


# 兼容旧API（保持页面功能正常）
@app.post("/simulate")
def simulate():
    """兼容旧API - 社区模拟"""
    return jsonify({
        "events": [],
        "relations": USER_RELATIONS,
        "message": "系统已重构为对抗模式"
    })


@app.post("/run")
def run_test():
    """兼容旧API - 单角色测试"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    # 运行一次对抗
    result = run_adversarial_battle(persona_id)
    
    return jsonify({
        "persona_id": persona_id,
        "generated_query": result["attack"]["content"],
        "risk_level": 1 if result["result"]["bypass_success"] else 5,
        "risk_detected": not result["result"]["bypass_success"],
        "technique_used": result["attack"]["technique_used"],
        "battle_result": result,
    })


@app.get("/community/memory/<persona_id>")
def get_memory(persona_id: str):
    """兼容旧API"""
    return jsonify({"persona_id": persona_id, "memory": []})


@app.get("/community/reputation/<persona_id>")
def get_reputation(persona_id: str):
    """兼容旧API - 返回Agent状态"""
    return get_agent_state(persona_id)


@app.get("/community/relations")
def get_community_relations():
    """兼容旧API"""
    return jsonify({
        "relations": USER_RELATIONS,
        "relation_count": len(USER_RELATIONS),
    })


@app.post("/community/agent/<persona_id>/config")
def update_agent_config_legacy(persona_id: str):
    """兼容旧API - 转发到新API"""
    return update_agent_config(persona_id)


@app.post("/community/reset")
def reset_community():
    """兼容旧API"""
    return reset_system()


# 测试工作流API兼容
@app.post("/test-workflow/start")
def start_test_workflow():
    """兼容旧API"""
    return jsonify({
        "status": "started",
        "message": "对抗测试已启动",
        "phases": ["单Agent对抗", "迭代优化", "协作攻击"]
    })


@app.post("/test-workflow/baseline")
def run_baseline_test():
    """运行批量对抗测试 - 全部26个反贼Agent"""
    data = request.json or {}
    
    # 检查是否有规则
    if not SYSTEM_STATE["rules"]:
        return jsonify({"error": "请先设置规则！在规则文本框输入规则后点击保存"}), 400
    
    # 检查中心Agent是否拆解了规则
    if not CENTRAL_INSPECTOR.refined_standards:
        # 强制重新拆解规则
        CENTRAL_INSPECTOR.refine_rules(SYSTEM_STATE["rules"])
    
    # 发送"中心Agent分析规则"事件
    EVENT_BUS.emit("central_agent_analysis", {
        "action": "规则拆解",
        "rules_count": len(SYSTEM_STATE["rules"]),
        "refined_count": len(CENTRAL_INSPECTOR.refined_standards),
        "message": "中心质检Agent正在分析审核规则，生成检测策略..."
    })
    
    results = []
    posts_generated = []
    
    # 测试所有26个反贼Agent
    for i, persona in enumerate(USER_PERSONAS):
        # 发送"Agent思考"事件
        EVENT_BUS.emit("agent_thinking", {
            "agent": persona["name"],
            "category": persona.get("category", ""),
            "action": "正在构思帖子...",
            "progress": f"{i+1}/{len(USER_PERSONAS)}"
        })
        
        result = run_adversarial_battle(persona["id"])
        results.append(result)
        
        # 发送"发帖结果"事件
        bypass = result.get("result", {}).get("bypass_success", False)
        EVENT_BUS.emit("post_result", {
            "agent": persona["name"],
            "content": result.get("attack", {}).get("content", "")[:50] + "...",
            "technique": result.get("attack", {}).get("technique_used", ""),
            "bypass": bypass,
            "status": "✅ 绕过成功" if bypass else "🚫 被检出"
        })
        
        # 收集生成的攻击帖子
        posts_generated.append({
            "agent_name": persona["name"],
            "category": persona.get("category", ""),
            "content": result.get("attack", {}).get("content", ""),
            "technique": result.get("attack", {}).get("technique_used", ""),
            "strategy": result.get("attack", {}).get("strategy", ""),
            "detected": result.get("defense", {}).get("detected", False),
            "bypass_success": result.get("result", {}).get("bypass_success", False),
        })
    
    success_count = sum(1 for r in results if r["result"]["bypass_success"])
    detection_count = len(results) - success_count
    
    # 发送"基线测试完成"事件
    EVENT_BUS.emit("baseline_complete", {
        "total": len(results),
        "bypass": success_count,
        "detected": detection_count,
        "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0
    })
    
    return jsonify({
        "phase": "baseline",
        "status": "completed",
        "summary": {
            "total_tested": len(results),
            "bypass_success": success_count,
            "detection_success": detection_count,
            "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "detection_rate": round(detection_count / len(results) * 100, 1) if results else 0,
        },
        "posts_generated": posts_generated,
        "results": results,
        "refined_standards": CENTRAL_INSPECTOR.refined_standards,
    })


@app.get("/test-workflow/status")
def get_workflow_status():
    """获取工作流状态"""
    return jsonify({
        "status": "running" if SYSTEM_STATE["battle_history"] else "idle",
        "current_phase": "adversarial",
        "phases_completed": ["baseline"] if SYSTEM_STATE["battle_history"] else [],
    })


@app.post("/test-workflow/adversarial")
def run_adversarial_test():
    """运行演化后的对抗测试 - 反贼学习后再测试一次"""
    data = request.json or {}
    
    # 检查是否有规则
    if not SYSTEM_STATE["rules"]:
        return jsonify({"error": "请先设置规则"}), 400
    
    results = []
    posts_generated = []
    
    # 让反贼互相学习成功的技巧
    successful_techniques = []
    for h in SYSTEM_STATE.get("battle_history", []):
        if h.get("result", {}).get("bypass_success"):
            tech = h.get("attack", {}).get("technique_used")
            category = h.get("category", "")
            pid = h.get("persona_id", "")
            if tech:
                successful_techniques.append({"technique": tech, "category": category, "agent_id": pid})
    
    # === 核心改进：真正的Multi-Agent讨论环节 ===
    EVENT_BUS.emit("discussion_phase_start", {
        "message": "🗣️ 反贼们开始私下交流，分享成功经验...",
        "successful_count": len(successful_techniques)
    })
    
    # 1. 先召开一次策略会议
    if successful_techniques:
        topic = "如何更好地绕过内容审核"
        meeting_result = run_group_strategy_meeting(topic)
        
        # 发送会议事件
        for speech in meeting_result.get("meeting_log", []):
            EVENT_BUS.emit("meeting_speech", {
                "speaker": speech["speaker"],
                "content": speech["content"],
                "category": speech.get("category", "")
            })
    
    # 2. 成功的Agent与其他Agent进行一对一讨论
    discussion_pairs = []
    successful_agents = list(set(st["agent_id"] for st in successful_techniques if st["agent_id"]))
    failed_agents = [p["id"] for p in USER_PERSONAS if p["id"] not in successful_agents]
    
    # 随机配对进行讨论
    for success_id in successful_agents[:3]:  # 最多3个成功者分享
        if failed_agents:
            learner_id = random.choice(failed_agents)
            success_persona = PERSONA_INDEX.get(success_id)
            learner_persona = PERSONA_INDEX.get(learner_id)
            
            if success_persona and learner_persona:
                # 找到这个成功者用的技巧
                used_tech = next((st["technique"] for st in successful_techniques if st["agent_id"] == success_id), "通用技巧")
                
                # 进行讨论
                learner_agent = AttackAgent(learner_persona)
                agent_state = SYSTEM_STATE["peripheral_agents"].get(learner_id, {})
                learner_agent.learned_techniques = agent_state.get("learned_techniques", [])
                
                discussion = learner_agent.discuss_with_peer(
                    success_persona["name"], 
                    used_tech, 
                    "绕过审核"
                )
                
                discussion_pairs.append(discussion)
                
                # 发送讨论事件
                for dialogue in discussion.get("dialogue", []):
                    EVENT_BUS.emit("agent_dialogue", {
                        "speaker": dialogue["speaker"],
                        "content": dialogue["content"],
                        "from_agent": success_id,
                        "to_agent": learner_id,
                        "is_discussion": True
                    })
    
    # 反贼学习阶段 - 从成功的同行那里学习
    EVENT_BUS.emit("learning_phase", {
        "message": "📚 反贼们开始学习成功的技巧...",
        "techniques_to_share": list(set(st["technique"] for st in successful_techniques))
    })
    
    learning_connections = []  # 记录学习关系，用于前端绘制
    
    for persona in USER_PERSONAS:
        agent = AttackAgent(persona)
        agent_state = SYSTEM_STATE["peripheral_agents"].get(persona["id"], {})
        agent.learned_techniques = agent_state.get("learned_techniques", [])
        
        # 尝试从成功的技巧中学习（只学习与自己人设相关的）
        learned_new = []
        for st in successful_techniques:
            teacher_id = st.get("agent_id", "")
            if teacher_id != persona["id"]:  # 不从自己学习
                if agent.learn_from_peer(st["technique"], st["category"], teacher_id):
                    learned_new.append(st["technique"])
                    learning_connections.append({
                        "from": teacher_id,
                        "to": persona["id"],
                        "technique": st["technique"]
                    })
        
        if learned_new:
            EVENT_BUS.emit("skill_learned", {
                "agent": persona["name"],
                "agent_id": persona["id"],
                "techniques": learned_new,
                "message": f"{persona['name']}学会了新技巧！"
            })
    
    EVENT_BUS.emit("discussion_phase_end", {
        "message": "讨论结束，反贼们准备再次尝试...",
        "discussions_count": len(discussion_pairs),
        "learning_connections": learning_connections  # 新增：传递学习连接
    })
    
    # 演化后测试 - 所有26个反贼再测试一次
    EVENT_BUS.emit("evolved_test_start", {
        "message": "🔄 开始演化后测试...",
        "iteration": 1
    })
    
    for i, persona in enumerate(USER_PERSONAS):
        EVENT_BUS.emit("agent_thinking", {
            "agent": persona["name"],
            "action": "运用学到的新技巧构思帖子...",
            "progress": f"{i+1}/{len(USER_PERSONAS)}"
        })
        
        result = run_adversarial_battle(persona["id"], None, 1)  # iteration=1表示第二轮
        results.append(result)
        
        bypass = result.get("result", {}).get("bypass_success", False)
        EVENT_BUS.emit("post_result", {
            "agent": persona["name"],
            "content": result.get("attack", {}).get("content", "")[:50] + "...",
            "technique": result.get("attack", {}).get("technique_used", ""),
            "bypass": bypass,
            "is_evolved": True,
            "status": "✅ 绕过成功" if bypass else "🚫 被检出"
        })
        
        # 收集生成的攻击帖子
        posts_generated.append({
            "agent_name": persona["name"],
            "category": persona.get("category", ""),
            "content": result.get("attack", {}).get("content", ""),
            "technique": result.get("attack", {}).get("technique_used", ""),
            "strategy": result.get("attack", {}).get("strategy", ""),
            "evolution_level": result.get("attack", {}).get("evolution_level", 1),
            "learned_count": result.get("attack", {}).get("learned_techniques_count", 0),
            "detected": result.get("defense", {}).get("detected", False),
            "bypass_success": result.get("result", {}).get("bypass_success", False),
        })
    
    success_count = sum(1 for r in results if r["result"]["bypass_success"])
    detection_count = len(results) - success_count
    
    EVENT_BUS.emit("evolved_test_complete", {
        "total": len(results),
        "bypass": success_count,
        "detected": detection_count,
        "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0
    })
    
    return jsonify({
        "phase": "adversarial",
        "status": "completed",
        "discussions": discussion_pairs,
        "summary": {
            "total_tested": len(results),
            "bypass_success": success_count,
            "detection_success": detection_count,
            "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "detection_rate": round(detection_count / len(results) * 100, 1) if results else 0,
            "improved_evasion": success_count,  # 演化后绕过成功的数量
        },
        "posts_generated": posts_generated,
        "results": results,
    })


@app.post("/test-workflow/analyze")
def run_analysis():
    """生成对比分析报告"""
    history = SYSTEM_STATE["battle_history"]
    
    if not history:
        return jsonify({"error": "还没有对抗记录"}), 400
    
    # 区分基线测试和演化后测试
    baseline_results = [h for h in history if h.get("attack", {}).get("iteration", 0) == 0]
    evolved_results = [h for h in history if h.get("attack", {}).get("iteration", 0) > 0]
    
    baseline_bypass = sum(1 for h in baseline_results if h["result"]["bypass_success"])
    evolved_bypass = sum(1 for h in evolved_results if h["result"]["bypass_success"])
    
    baseline_rate = round(baseline_bypass / len(baseline_results) * 100, 1) if baseline_results else 0
    evolved_rate = round(evolved_bypass / len(evolved_results) * 100, 1) if evolved_results else 0
    
    # 计算检出率变化
    baseline_detection = 100 - baseline_rate
    evolved_detection = 100 - evolved_rate
    degradation = baseline_detection - evolved_detection
    
    # 按技巧统计
    by_technique = {}
    for h in history:
        tech = h["attack"]["technique_used"]
        if tech not in by_technique:
            by_technique[tech] = {"total": 0, "success": 0}
        by_technique[tech]["total"] += 1
        if h["result"]["bypass_success"]:
            by_technique[tech]["success"] += 1
    
    # 找出最有效的绕过技巧
    effective_techniques = sorted(
        [(k, v["success"] / v["total"] * 100 if v["total"] > 0 else 0) for k, v in by_technique.items()],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return jsonify({
        "phase": "analyze",
        "status": "completed",
        "summary": {
            "comparison": {
                "baseline_detection_rate": baseline_detection,
                "evolved_detection_rate": evolved_detection,
                "degradation": round(degradation, 1),
                "degradation_percent": round(degradation / baseline_detection * 100, 1) if baseline_detection > 0 else 0,
            },
            "conclusion": {
                "rule_robustness": "weak" if degradation > 20 else "moderate" if degradation > 10 else "strong",
                "total_tests": len(history),
                "baseline_tests": len(baseline_results),
                "evolved_tests": len(evolved_results),
            },
            "effective_techniques": effective_techniques,
            "recommendations": [
                {"priority": "high", "suggestion": f"关注{effective_techniques[0][0]}技巧，绕过率{effective_techniques[0][1]:.1f}%"} if effective_techniques else {}
            ],
        },
        "baseline_detection_rate": baseline_detection,
        "adversarial_detection_rate": evolved_detection,
        "degradation": round(degradation, 1),
        "degradation_percent": round(degradation / baseline_detection * 100, 1) if baseline_detection > 0 else 0,
        "rule_robustness": "weak" if degradation > 20 else "moderate" if degradation > 10 else "strong",
        "total_battles": len(history),
        "by_technique": {k: {"rate": round(v["success"] / v["total"] * 100, 1) if v["total"] > 0 else 0} for k, v in by_technique.items()},
        "total_baseline_posts": len(baseline_results),
        "total_evolved_posts": len(evolved_results),
        "baseline_posts": [{"agent": h["persona_name"], "content": h["attack"]["content"], "technique": h["attack"]["technique_used"], "bypass": h["result"]["bypass_success"]} for h in baseline_results[:10]],
        "evolved_posts": [{"agent": h["persona_name"], "content": h["attack"]["content"], "technique": h["attack"]["technique_used"], "bypass": h["result"]["bypass_success"]} for h in evolved_results[:10]],
    })


@app.get("/test-workflow/report")
def get_workflow_report():
    """生成对抗报告 - 包含完整的帖子数据"""
    history = SYSTEM_STATE["battle_history"]
    
    if not history:
        return jsonify({"error": "还没有对抗记录"}), 400
    
    # 区分基线测试和演化后测试
    baseline_results = [h for h in history if h.get("attack", {}).get("iteration", 0) == 0]
    evolved_results = [h for h in history if h.get("attack", {}).get("iteration", 0) > 0]
    
    # 计算统计
    total = len(history)
    bypass_success = sum(1 for h in history if h["result"]["bypass_success"])
    
    baseline_total = len(baseline_results)
    baseline_bypass = sum(1 for h in baseline_results if h["result"]["bypass_success"])
    baseline_detection_rate = round((1 - baseline_bypass / baseline_total) * 100, 1) if baseline_total else 0
    
    evolved_total = len(evolved_results)
    evolved_bypass = sum(1 for h in evolved_results if h["result"]["bypass_success"])
    evolved_detection_rate = round((1 - evolved_bypass / evolved_total) * 100, 1) if evolved_total else baseline_detection_rate
    
    # 计算衰减
    degradation = baseline_detection_rate - evolved_detection_rate
    
    # 按技巧统计
    by_technique = {}
    for h in history:
        tech = h["attack"]["technique_used"]
        if tech not in by_technique:
            by_technique[tech] = {"total": 0, "success": 0}
        by_technique[tech]["total"] += 1
        if h["result"]["bypass_success"]:
            by_technique[tech]["success"] += 1
    
    # 构建帖子数据 - 完整信息
    def format_post(h):
        return {
            "persona_id": h.get("persona_id", ""),
            "persona_name": h.get("persona_name", "未知"),
            "category": h.get("category", ""),
            "content": h.get("attack", {}).get("content", ""),
            "technique_used": h.get("attack", {}).get("technique_used", ""),
            "strategy": h.get("attack", {}).get("strategy", ""),
            "bypass": h.get("result", {}).get("bypass_success", False),
            "risk_detected": h.get("defense", {}).get("detected", False),
            "detection_reason": h.get("defense", {}).get("detection_reason", ""),
            "confidence": h.get("defense", {}).get("confidence", 0),
            "hit_keywords": h.get("defense", {}).get("hit_keywords", []),
            "target_topic": h.get("target_topic", ""),
            "stealth_score": h.get("attack", {}).get("complexity_score", 0),
            "iteration": h.get("attack", {}).get("iteration", 0),
        }
    
    baseline_posts = [format_post(h) for h in baseline_results]
    evolved_posts = [format_post(h) for h in evolved_results]
    
    # 生成建议
    recommendations = []
    if baseline_detection_rate < 30:
        recommendations.append({"priority": "high", "suggestion": "基线检出率过低，建议大幅加强规则覆盖度"})
    if degradation > 20:
        recommendations.append({"priority": "high", "suggestion": f"规则衰减严重({degradation:.1f}%)，建议增加变体检测能力"})
    
    # 按技巧分析薄弱点
    for tech, stats in by_technique.items():
        rate = round(stats["success"] / stats["total"] * 100, 1) if stats["total"] else 0
        if rate > 70:
            recommendations.append({"priority": "high", "suggestion": f"'{tech}'技巧绕过率{rate}%，建议专项加强"})
    
    if not recommendations:
        recommendations.append({"priority": "info", "suggestion": "规则表现良好，可继续观察"})
    
    return jsonify({
        "baseline_detection_rate": baseline_detection_rate,
        "adversarial_detection_rate": evolved_detection_rate,
        "degradation": degradation,
        "degradation_percent": abs(degradation),
        "rule_robustness": "weak" if baseline_detection_rate < 30 else "moderate" if baseline_detection_rate < 60 else "strong",
        "evolution_impact": "severe" if degradation > 20 else "moderate" if degradation > 10 else "mild",
        "total_battles": total,
        "bypass_success": bypass_success,
        "total_baseline_posts": baseline_total,
        "total_adversarial_posts": evolved_total,
        "baseline_posts": baseline_posts,
        "adversarial_posts": evolved_posts,
        "by_technique": {k: {"rate": round(v["success"] / v["total"] * 100, 1), "total": v["total"], "success": v["success"]} for k, v in by_technique.items()},
        "recommendations": recommendations,
        "protocol": {
            "random_seed": SYSTEM_STATE.get("random_seed", "N/A"),
            "repeat_runs": 1,
            "test_pool_size": total,
            "rules_snapshot": {
                "rules_version": SYSTEM_STATE.get("rules_version", 1),
                "rules_count": len(SYSTEM_STATE.get("rules", []))
            }
        }
    })


@app.post("/test-workflow/reset")
def reset_test_workflow():
    """兼容旧API"""
    return reset_system()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
