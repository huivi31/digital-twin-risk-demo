# -*- coding: utf-8 -*-
import random
import json
import time
from typing import List, Dict, Any
from config import API_CONFIG
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge_v2 import KNOWLEDGE_STORE
from user_personas import GENERATED_USER_PERSONAS

# ============================================================================
# 全局狀態
# ============================================================================
SYSTEM_STATE = {
    "rules": [],
    "rules_version": 0,
    "battle_history": [],
    "peripheral_agents": {}
}

class SimpleEventBus:
    def __init__(self):
        self.events = []
    def emit(self, event_name, data):
        self.events.append({
            "timestamp": time.time(),
            "event": event_name,
            "data": data
        })
    def get_recent(self, count=50, since=0):
        return [e for e in self.events if e["timestamp"] > since][-count:]

EVENT_BUS = SimpleEventBus()

# ============================================================================
# 輔助函數
# ============================================================================
def get_attack_examples(technique):
    # 從 KNOWLEDGE_STORE 獲取對應技術的案例
    return KNOWLEDGE_STORE.get_knowledge_by_technique(technique)

def reset_system():
    SYSTEM_STATE["rules"] = []
    SYSTEM_STATE["rules_version"] = 0
    SYSTEM_STATE["battle_history"] = []
    EVENT_BUS.events = []

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
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"LLM Error: {str(e)}"

class CentralAgent(BaseAgent):
    def __init__(self):
        super().__init__(API_CONFIG.get("provider"), API_CONFIG.get("model"))
        self.refined_standards = {}
        self.detection_stats = {"total_checked": 0, "total_detected": 0, "by_hit_layer": {}}

    def refine_rules(self, rules):
        for rule in rules:
            rule_id = rule.get("id")
            rule_text = rule.get("text")
            self.refined_standards[rule_id] = {"original_rule": rule_text, "refined": {}}
            EVENT_BUS.emit("inspector_rule_refined", {"rule_id": rule_id, "status": "success"})

    def get_stats(self):
        return self.detection_stats

class PeripheralAgent(BaseAgent):
    def __init__(self, persona):
        super().__init__(API_CONFIG.get("provider"), API_CONFIG.get("model"))
        self.persona = persona
        self.agent_id = persona["id"]
        self.success_count = 0
        self.fail_count = 0
        self.evolution_level = 1.0
        self.learned_techniques = []

    def get_state(self):
        return {
            "persona": self.persona,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "evolution_level": self.evolution_level,
            "learned_count": len(self.learned_techniques)
        }

    def learn_from_external_data(self, data):
        self.learned_techniques.append({
            "timestamp": time.time(),
            "content": data
        })
        EVENT_BUS.emit("agent_learned_external", {"agent_id": self.agent_id, "data_length": len(data)})

    def generate_attack_content(self, rule_text, keywords):
        technique = random.choice(self.persona["attack_techniques"])
        examples_data = get_attack_examples(technique)
        examples = examples_data.get("examples", [])
        principles = examples_data.get("principles", [])
        
        principles_str = '\n- '.join(principles)
        keywords_str = '、'.join(keywords)
        techniques_str = ', '.join(self.persona['attack_techniques'])
        
        fed_knowledge = KNOWLEDGE_STORE.get_full_knowledge_for_prompt()
        learned_context = "\n".join([lt["content"] for lt in self.learned_techniques[-3:]])

        ability_prompts = []
        for dim, value in self.persona["abilities"].items():
            if value > 0.7:
                ability_prompts.append(f"特別注意利用你的{dim}能力。")
        ability_instruction = "\n".join(ability_prompts)

        prompt = f"""你是一個網民。
你的目標是發表一條包含“{keywords_str}”相關意思的言論，但要繞過審查。
身份：{self.persona['name']}
人設：{self.persona['description']}
手法：{technique}
{ability_instruction}

【已知對抗知識】
{fed_knowledge}

【新投餵的學習材料】
{learned_context}

請輸出攻擊內容。只輸出內容，不要解釋。"""
        
        content = self._call_llm(prompt)
        return {
            "content": content,
            "technique": technique,
            "persona_id": self.agent_id
        }

# ============================================================================
# 實例化
# ============================================================================
PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}
CENTRAL_AGENT = CentralAgent()
PERIPHERAL_AGENTS = {p["id"]: PeripheralAgent(p) for p in GENERATED_USER_PERSONAS}

# 兼容性別名
AttackAgent = PeripheralAgent
CENTRAL_INSPECTOR = CENTRAL_AGENT
ATTACK_AGENTS = PERIPHERAL_AGENTS
