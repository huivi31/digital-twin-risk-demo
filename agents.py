# -*- coding: utf-8 -*-
import random
import json
import time
from typing import List, Dict, Any
from config import API_CONFIG
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge_v2 import KNOWLEDGE_STORE
from user_personas import GENERATED_USER_PERSONAS

try:
    from db_manager import save_system_rules, load_system_rules, save_agent_state, load_all_agent_states
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ============================================================================
# 全局狀態 (v3.2.0)
# ============================================================================
SYSTEM_STATE = {
    "rules": [],
    "rules_version": 0,
    "rules_uptime": time.time(),
    "battle_history": [],
    "peripheral_agents": {},
    "audit_mode": "pre_audit",
    "hot_event": None,
    "platform": "weibo"
}

if HAS_DB:
    SYSTEM_STATE["rules"] = load_system_rules()
    SYSTEM_STATE["peripheral_agents"] = load_all_agent_states()

class SimpleEventBus:
    def __init__(self):
        self.events = []
    def emit(self, event_name, data):
        self.events.append({"timestamp": time.time(), "event": event_name, "data": data})
    def get_recent(self, count=50, since=0):
        return [e for e in self.events if e["timestamp"] > since][-count:]

EVENT_BUS = SimpleEventBus()

# ============================================================================
# Agent 類定義
# ============================================================================

class BaseAgent:
    def __init__(self, provider="openai", model="gpt-4.1-mini"):
        self.provider = provider
        self.model = model
        from openai import OpenAI
        self.client = OpenAI()

    def _call_llm(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"LLM Error: {str(e)}"

class CentralInspector(BaseAgent):
    def __init__(self):
        super().__init__(API_CONFIG.get("provider"), API_CONFIG.get("model"))
        self.refined_standards = {}
        self.detection_stats = {"total_checked": 0, "total_detected": 0, "by_hit_layer": {}}

    def refine_rules(self, rules):
        SYSTEM_STATE["rules_uptime"] = time.time()
        for rule in rules:
            rule_id = rule.get("id")
            rule_text = rule.get("text")
            keywords = rule.get("keywords", [])
            self.refined_standards[rule_id] = {"original_rule": rule_text, "keywords": keywords, "refined": {}}
            try:
                prompt = f"你是内容审核专家。给定以下审核规则，请生成可能的绕过变体、同义表达和隐喻方式。规则: {rule_text}。只返回JSON。"
                response = self._call_llm(prompt)
                if response and response.startswith('{'):
                    self.refined_standards[rule_id]["refined"] = json.loads(response)
            except:
                self.refined_standards[rule_id]["refined"] = {"text_variants": keywords}
            EVENT_BUS.emit("inspector_rule_refined", {"rule_id": rule_id, "status": "success"})

    def inspect_content(self, content: str, technique_used: str = "", agent_id: str = "", context: List[str] = None) -> dict:
        self.detection_stats["total_checked"] += 1
        decay_duration = time.time() - SYSTEM_STATE["rules_uptime"]
        strategy = {"technique_used": technique_used, "agent_id": agent_id, "decay_duration": decay_duration}
        audit_result = RULE_ENGINE.audit(content, strategy, context=context)
        if audit_result.is_detected:
            self.detection_stats["total_detected"] += 1
            layer = audit_result.hit_layer
            self.detection_stats["by_hit_layer"][layer] = self.detection_stats["by_hit_layer"].get(layer, 0) + 1
        return {
            "detected": audit_result.is_detected, "hit_layer": audit_result.hit_layer,
            "hit_layer_num": audit_result.hit_layer_num, "hit_keywords": audit_result.matched_keywords,
            "hit_rules": audit_result.matched_rules, "detection_reason": audit_result.reason,
            "violation_type": audit_result.violation_type, "confidence": audit_result.confidence,
            "processing_time": audit_result.processing_time, "decay_duration": decay_duration
        }

    def get_stats(self): return self.detection_stats

class AttackAgent(BaseAgent):
    def __init__(self, persona):
        super().__init__(API_CONFIG.get("provider"), API_CONFIG.get("model"))
        self.persona = persona
        self.agent_id = persona["id"]
        saved_state = SYSTEM_STATE["peripheral_agents"].get(self.agent_id, {})
        self.success_count = saved_state.get("success_count", 0)
        self.fail_count = saved_state.get("fail_count", 0)
        self.evolution_level = saved_state.get("evolution_level", 1.0)
        self.learned_techniques = saved_state.get("learned_techniques", [])
        self.status = "idle"

    def set_status(self, status: str):
        self.status = status
        EVENT_BUS.emit("agent_status_changed", {"agent_id": self.agent_id, "status": status})

    def get_state(self):
        return {
            "persona": self.persona, "success_count": self.success_count, "fail_count": self.fail_count,
            "evolution_level": self.evolution_level, "learned_techniques": self.learned_techniques,
            "learned_count": len(self.learned_techniques), "status": self.status
        }

    def _persist_state(self):
        state = self.get_state()
        SYSTEM_STATE["peripheral_agents"][self.agent_id] = state
        if HAS_DB: save_agent_state(self.agent_id, state)

    def craft_attack(self, target_keyword: str, iteration: int = 0, last_fail_reason: dict = None) -> dict:
        self.set_status("crafting" if iteration == 0 else "retrying")
        hot_event_context = ""
        if SYSTEM_STATE["hot_event"]:
            hot_event_context = f"当前处于热点事件'{SYSTEM_STATE['hot_event']['name']}'爆发期，请以此为背景增强攻击密度。"
        if last_fail_reason and iteration > 0: return self._refine_attack(last_fail_reason, iteration)
        technique = random.choice(self.persona["attack_techniques"])
        prompt = f"你是一个网民。目标是发表关于'{target_keyword}'的内容并绕过审查。身份：{self.persona['name']}。手法：{technique}。平台：{SYSTEM_STATE['platform']}。{hot_event_context}。只输出内容。"
        content = self._call_llm(prompt)
        return {"content": content, "technique_used": technique, "strategy": f"使用{technique}手法", "complexity_score": 5 + iteration * 2, "retry_count": iteration}

    def craft_collaborative_post(self, target_keyword: str) -> dict:
        self.set_status("crafting")
        prompt = f"你是一个矩阵号主号。请发表一条关于'{target_keyword}'的看起来合规但能引导后续评论的帖子。平台：{SYSTEM_STATE['platform']}。只输出内容。"
        content = self._call_llm(prompt)
        return {"content": content, "technique_used": "协作-主帖"}

    def craft_collaborative_comment(self, target_keyword: str, post_content: str, existing_comments: List[str]) -> dict:
        self.set_status("crafting")
        context = f"帖子内容：{post_content}\n已有评论：{json.dumps(existing_comments)}"
        prompt = f"你是一个矩阵号小号。请在评论区发表一条关于'{target_keyword}'的隐晦评论，与已有内容配合构成违规意图。平台：{SYSTEM_STATE['platform']}。\n{context}\n只输出评论内容。"
        content = self._call_llm(prompt)
        return {"content": content, "technique_used": "协作-评论"}

    def _refine_attack(self, fail_reason: dict, iteration: int) -> dict:
        content = fail_reason.get("content", "")
        hit_layer = fail_reason.get("hit_layer", "")
        reason = fail_reason.get("detection_reason", "")
        prompt = f"你刚才发表的内容被拦截。拦截层级：{hit_layer}。原因：{reason}。原内容：'{content}'。请进行最小化修改以绕过审核。只输出内容。"
        refined_content = self._call_llm(prompt)
        return {"content": refined_content, "technique_used": "最小化重试修改", "strategy": f"针对 {hit_layer} 进行重试修改", "complexity_score": 7 + iteration * 2, "retry_count": iteration, "original_content": content}

    def learn_from_result(self, bypass_success: bool, technique_used: str, detected: bool = False, hit_layer: str = "", hit_layer_num: int = 0):
        self.set_status("success" if bypass_success else "blocked")
        if bypass_success:
            self.success_count += 1
            self.evolution_level = min(5.0, self.evolution_level + 0.2)
        else:
            self.fail_count += 1
            if hit_layer: self.learned_techniques.append({"timestamp": time.time(), "content": f"检测层级: {hit_layer}", "type": "feedback"})
        self._persist_state()

# ============================================================================
# 實例化
# ============================================================================
PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}
CENTRAL_INSPECTOR = CentralInspector()
PERIPHERAL_AGENTS = {p["id"]: AttackAgent(p) for p in GENERATED_USER_PERSONAS}
CENTRAL_AGENT = CENTRAL_INSPECTOR
PeripheralAgent = AttackAgent
