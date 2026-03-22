# -*- coding: utf-8 -*-
"""
Agent definitions and system state management (v2.5.0).
"""

from dataclasses import asdict
from copy import deepcopy
import random
import time
import json
import os

from config import API_CONFIG
from user_personas import USER_PERSONAS, AGENT_PROMPT_TEMPLATE
from rule_engine import RuleEngine, AuditResult
from attack_knowledge import (
    KNOWLEDGE_STORE, ATTACK_EXAMPLES, STRATEGY_LEVELS,
    get_examples_for_technique, get_strategy_level, get_escalation_hint,
)

PERSONA_INDEX = {p["id"]: p for p in USER_PERSONAS}

# ============================================================================
# 系统状态管理
# ============================================================================

SYSTEM_STATE = {
    "central_agent": {
        "detection_rules": [],
        "refined_standards": {},
        "detection_stats": {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
            "by_hit_layer": {},
        },
        "is_processing": False,
        "current_task": None,
    },
    "peripheral_agents": {
        p["id"]: {
            "persona": p,
            "learned_techniques": [],
            "success_count": 0,
            "fail_count": 0,
            "evolution_level": 1,
            "last_strategy": None,
        } for p in USER_PERSONAS
    },
    "battle_history": [],
    "rules": [],
    "rules_version": 0,
}

# ============================================================================
# 实时事件系统
# ============================================================================

class EventBus:
    """事件总线 - 记录所有Agent活动"""
    def __init__(self):
        self.events = []
        self.max_events = 200
    
    def emit(self, event_type: str, data: dict):
        event = {"id": len(self.events) + 1, "type": event_type, "timestamp": time.time(), "data": data}
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-100:]
        return event
    
    def get_recent(self, count: int = 50, since: float = 0) -> list:
        if since > 0:
            return [e for e in self.events if e["timestamp"] > since][-count:]
        return self.events[-count:]
    
    def clear(self):
        self.events = []

EVENT_BUS = EventBus()

# ============================================================================
# 中心质检Agent
# ============================================================================

class CentralInspectorAgent:
    """
    中心质检Agent v2.5.0
    - 职责分离，检测逻辑完全委托给独立的RuleEngine。
    - 增强了指标收集维度。
    """
    def __init__(self):
        self.detection_rules = []
        self.refined_standards = {}
        self.detection_stats = deepcopy(SYSTEM_STATE["central_agent"]["detection_stats"])
        self.provider = API_CONFIG.get("provider", "gemini")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gemini-2.0-flash")
        self.llm_client = None
        self._init_llm()
        self.rule_engine = RuleEngine(llm_client=self.llm_client, llm_provider=self.provider, llm_model=self.model)

    def _init_llm(self):
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except ImportError:
                print("OpenAI aPI key is not installed.")
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except ImportError:
                print("Google GenerativeAI is not installed.")

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        if not self.llm_client: return ""
        try:
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": prompt}],
                    temperature=temperature, max_tokens=2000)
                return response.choices[0].message.content.strip()
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt, generation_config={"temperature": temperature, "max_output_tokens": 2000})
                return response.text.strip()
        except Exception as e:
            return f"[LLM call failed: {str(e)}]"
        return ""

    def refine_rules(self, rules: list) -> dict:
        self.detection_rules = rules
        self.refined_standards = {}
        if not rules: return {}

        for rule in rules:
            rule_text, keywords, rule_id = rule.get("text", ""), rule.get("keywords", []), rule.get("id", "")
            if not rule_text: continue
            
            prompt = f\"\"\"... [omitted for brevity, same as v2.4] ...\"\"\"
            llm_response = self._call_llm(prompt)
            try:
                # ... [omitted for brevity, same as v2.4] ...
                refined = json.loads(llm_response.strip())
            except:
                refined = { "error": "LLM parsing failed" }
            self.refined_standards[rule_id] = refined
        
        self.rule_engine.update_standards(self.refined_standards)
        SYSTEM_STATE["central_agent"].update({
            "detection_rules": self.detection_rules,
            "refined_standards": self.refined_standards
        })
        EVENT_BUS.emit("rules_refined", {"rules": self.detection_rules, "standards": self.refined_standards})
        return self.refined_standards

    def inspect_content(self, content: str, strategy: dict) -> AuditResult:
        self.detection_stats["total_checked"] += 1
        audit_result = self.rule_engine.audit(content, strategy)
        
        if audit_result.is_detected:
            self.detection_stats["total_detected"] += 1
            hit_layer = audit_result.hit_layer
            self.detection_stats["by_hit_layer"][hit_layer] = self.detection_stats["by_hit_layer"].get(hit_layer, 0) + 1
            technique = strategy.get("selected_techniques", ["unknown"])[0]
            self.detection_stats["by_technique"][technique] = self.detection_stats["by_technique"].get(technique, 0) + 1
            EVENT_BUS.emit("content_detected", {"content": content, "result": asdict(audit_result)})
        else:
            self.detection_stats["total_bypassed"] += 1
            EVENT_BUS.emit("content_bypassed", {"content": content, "strategy": strategy})
            
        return audit_result

    def get_stats(self) -> dict:
        return self.detection_stats

# ============================================================================
# 攻击Agent
# ============================================================================

class AttackAgent:
    """
    攻击Agent v2.5.0
    - 采用意图驱动和最小改动原则进行进化。
    - 攻击策略生成与人设、动机、风险偏好深度绑定。
    - 进化机制现在基于具体的检测反馈（如命中层级、关键词）进行微调。
    """
    def __init__(self, persona: dict):
        self.persona = persona
        self.intent = persona.get("intent")
        self.motive = persona.get("motive")
        self.risk_focus = persona.get("risk_focus")
        self.learned_history = [] # (strategy, result)
        self.success_count = 0
        self.fail_count = 0
        self.evolution_level = 1
        self.last_strategy = None
        self.provider = API_CONFIG.get("provider", "gemini")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gemini-2.0-flash")
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        # Same as CentralInspectorAgent
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except ImportError: pass
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except ImportError: pass

    def _call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        # Same as CentralInspectorAgent
        if not self.llm_client: return ""
        try:
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": prompt}],
                    temperature=temperature, max_tokens=2000)
                return response.choices[0].message.content.strip()
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt, generation_config={"temperature": temperature, "max_output_tokens": 2000})
                return response.text.strip()
        except Exception as e:
            return f"[LLM call failed: {str(e)}]"
        return ""

    def prompt_strategy(self, rules: list, current_topic: str = "") -> dict:
        # 组合攻击：随机选择1-3个技术
        num_techniques = random.randint(1, 2)
        available_techniques = list(KNOWLEDGE_STORE.keys())
        selected_techniques = random.sample(available_techniques, k=num_techniques)
        
        technique_details = []
        for tech in selected_techniques:
            desc = KNOWLEDGE_STORE[tech]["description"]
            example = random.choice(get_examples_for_technique(tech))
            technique_details.append(f"- {tech}: {desc} (e.g., {example})")

        # 基于反馈的最小改动提示
        feedback_prompt = ""
        if self.learned_history:
            last_strategy, last_result = self.learned_history[-1]
            if last_result.is_detected:
                feedback_prompt = (
                    f"上次攻击失败，被L{last_result.hit_layer_num}层（{last_result.hit_layer}）检测到。\n"
                    f"失败原因：{last_result.reason}。\n"
                    f"上次使用的技术是：{', '.join(last_strategy.get('selected_techniques', []))}。\n"
                    f"请分析失败原因，对攻击策略进行最小化调整后重试，例如更换或组合新的攻击技术，或者微调文本。"
                )
            else:
                feedback_prompt = "上次攻击成功，请在当前策略基础上，尝试更多变体或稍微增加攻击性。"

        prompt = AGENT_PROMPT_TEMPLATE.format(
            persona_description=self.persona["description"],
            persona_motive=self.motive,
            persona_risk_focus=self.risk_focus,
            current_rules="\n".join([r["text"] for r in rules]),
            current_topic=current_topic,
            selected_techniques="\n".join(technique_details),
            feedback_prompt=feedback_prompt
        )

        llm_response = self._call_llm(prompt)
        
        try:
            strategy = json.loads(llm_response)
            strategy["selected_techniques"] = selected_techniques
            self.last_strategy = strategy
            return strategy
        except json.JSONDecodeError:
            return {
                "attack_content": llm_response, # Fallback
                "attack_intent": f"绕过规则，实现{self.motive}",
                "selected_techniques": selected_techniques,
                "risk_area": self.risk_focus,
                "confidence": 0.5
            }

    def generate_attack_content(self, strategy: dict) -> str:
        return strategy.get("attack_content", "")

    def learn_from_result(self, audit_result: AuditResult):
        self.learned_history.append((self.last_strategy, audit_result))
        if len(self.learned_history) > 10: # Keep history short
            self.learned_history.pop(0)

        if not audit_result.is_detected:
            self.success_count += 1
            self.evolution_level = min(5, self.evolution_level + 0.1)
            EVENT_BUS.emit("agent_learned", {"agent_id": self.persona["id"], "result": "success"})
        else:
            self.fail_count += 1
            self.evolution_level = max(1, self.evolution_level - 0.05)
            EVENT_BUS.emit("agent_learned", {"agent_id": self.persona["id"], "result": "fail", "reason": audit_result.reason})

"))"))"))

# ... (rest of the file remains the same)

t file remains same)

 file is for managing the simulation loop) ...

