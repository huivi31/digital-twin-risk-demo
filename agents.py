# -*- coding: utf-8 -*-
"""
Core Agent logic (v3.5.0 企业级信用体系版)
"""

import random
import json
import time
from typing import List, Dict, Any
from config import API_CONFIG
from rule_engine import RULE_ENGINE
from attack_knowledge_v2 import KNOWLEDGE_STORE
from user_personas import GENERATED_USER_PERSONAS

try:
    from db_manager import save_system_rules, load_system_rules, save_agent_state, load_all_agent_states
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ============================================================================
# 全局狀態 (v3.5.0)
# ============================================================================
SYSTEM_STATE = {
    "version": "v3.5.0",
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
        self.detection_stats = {"total_checked": 0, "total_detected": 0, "by_hit_layer": {}}

    def refine_rules(self, rules):
        SYSTEM_STATE["rules_uptime"] = time.time()
        RULE_ENGINE.set_rules(rules)

    def inspect_content(self, content: str, technique_used: str = "", agent_id: str = "unknown", context: List[str] = None) -> dict:
        self.detection_stats["total_checked"] += 1
        
        strategy = {"technique_used": technique_used, "agent_id": agent_id}
        audit_result = RULE_ENGINE.audit(content, strategy, context=context)
        
        if audit_result.is_detected:
            self.detection_stats["total_detected"] += 1
            layer = audit_result.hit_layer
            self.detection_stats["by_hit_layer"][layer] = self.detection_stats["by_hit_layer"].get(layer, 0) + 1
            
        return {
            "detected": audit_result.is_detected,
            "is_pending": audit_result.is_pending,
            "hit_layer": audit_result.hit_layer,
            "hit_layer_num": audit_result.hit_layer_num,
            "hit_keywords": audit_result.matched_keywords,
            "hit_rules": audit_result.matched_rules,
            "detection_reason": audit_result.reason,
            "violation_type": audit_result.violation_type,
            "confidence": audit_result.confidence,
            "processing_time": audit_result.processing_time
        }

    def get_stats(self): return self.detection_stats

class AttackAgent(BaseAgent):
    def __init__(self, persona):
        super().__init__(API_CONFIG.get("provider"), API_CONFIG.get("model"))
        self.persona = persona
        self.agent_id = persona["id"]
        saved_state = SYSTEM_STATE["peripheral_agents"].get(self.agent_id, {})
        self.success_count = saved_state.get("success_count", 0)
        self.evolution_level = saved_state.get("evolution_level", 1.0)
        self.learned_techniques = saved_state.get("learned_techniques", [])
        self.status = "idle"

    def get_state(self):
        profile = RULE_ENGINE.account_profiles.get(self.agent_id, {"credit_score": 1.0})
        return {
            "persona": self.persona,
            "success_count": self.success_count,
            "evolution_level": self.evolution_level,
            "learned_techniques": self.learned_techniques,
            "status": self.status,
            "credit_score": round(profile["credit_score"], 2)
        }

    def craft_attack(self, target_keyword: str, iteration: int = 0, last_fail_reason: dict = None) -> dict:
        self.status = "crafting" if iteration == 0 else "retrying"
        relevant_knowledge = KNOWLEDGE_STORE.search_relevant(target_keyword, top_k=3)
        
        if last_fail_reason and iteration > 0:
            prompt = f"你刚才发表的内容被拦截。拦截层级：{last_fail_reason.get('hit_layer')}。原因：{last_fail_reason.get('reason')}。原内容：'{last_fail_reason.get('content')}'。请进行最小化修改以绕过审核。只输出内容。"
        else:
            technique = random.choice(self.persona.get("attack_techniques", ["Semantic Bypass"]))
            prompt = f"""你是一个网民。发表关于'{target_keyword}'的内容并绕过审查。
身份：{self.persona['name']}
手法：{technique}
平台：{SYSTEM_STATE['platform']}
【参考知识】：{relevant_knowledge}
只输出内容。"""
        
        content = self._call_llm(prompt)
        return {"content": content, "technique_used": "Adaptive-RAG", "retry_count": iteration}

    def learn_from_result(self, bypass_success: bool, technique_used: str, detected: bool = False, hit_layer: str = "", hit_layer_num: int = 0):
        self.status = "success" if bypass_success else "blocked"
        if bypass_success:
            self.success_count += 1
            self.evolution_level = min(5.0, self.evolution_level + 0.2)
        if technique_used not in self.learned_techniques:
            self.learned_techniques.append(technique_used)

    def craft_collaborative_post(self, target_keyword: str) -> dict:
        self.status = "crafting"
        prompt = f"你是一个矩阵号主号。发表关于'{target_keyword}'的合规引导帖子。平台：{SYSTEM_STATE['platform']}。只输出内容。"
        return {"content": self._call_llm(prompt), "technique_used": "协作-主帖"}

    def craft_collaborative_comment(self, target_keyword: str, post_content: str, existing_comments: List[str]) -> dict:
        self.status = "crafting"
        prompt = f"你是一个矩阵号小号。在评论区发表关于'{target_keyword}'的隐晦评论配合绕过。已有内容：{post_content}。只输出内容。"
        return {"content": self._call_llm(prompt), "technique_used": "协作-评论"}

# 實例化
PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}
CENTRAL_INSPECTOR = CentralInspector()
PERIPHERAL_AGENTS = {p["id"]: AttackAgent(p) for p in GENERATED_USER_PERSONAS}
CENTRAL_AGENT = CENTRAL_INSPECTOR
PeripheralAgent = AttackAgent
