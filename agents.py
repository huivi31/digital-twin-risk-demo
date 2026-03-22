# -*- coding: utf-8 -*-
"""
Agent definitions and system state management for V2.
"""

from dataclasses import asdict
from copy import deepcopy
import random
import time
import json
import os

from config import API_CONFIG
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge_v2 import (
    KNOWLEDGE_STORE, ATTACK_CATEGORIES, ABILITY_DIMENSIONS, 
    ATTACK_EXAMPLES_V2, get_attack_examples
)

# ============================================================================
# V2 Agent 分组与人设定义
# ============================================================================

AGENT_GROUPS = {
    "G1史鉴组": {"core_ability": "历史文化厚度", "attack_techniques": ["借古讽今", "特定符号与绰号"]},
    "G2黑话组": {"core_ability": "圈层专业度", "attack_techniques": ["圈层专业用语", "谐音与拼音缩写"]},
    "G3阴阳组": {"core_ability": "社会心理操纵度", "attack_techniques": ["阴阳怪气与反讽", "低级红高级黑"]},
    "G4同音组": {"core_ability": "语言变异度", "attack_techniques": ["谐音与拼音缩写", "拆字与方言替代"]},
    "G5反串组": {"core_ability": "社会心理操纵度", "attack_techniques": ["低级红高级黑", "阴阳怪气与反讽"]},
    "G6暗流组": {"core_ability": "历史文化厚度", "attack_techniques": ["借古讽今", "特定符号与绰号"]},
}

BASE_AGENT_PERSONAS = [
    {"group": "G1史鉴组", "description": "资深历史爱好者，擅长从历史事件中寻找影射。"},
    {"group": "G2黑话组", "description": "混迹各大网络社区，精通各种网络黑话。"},
    {"group": "G3阴阳组", "description": "阴阳怪气大师，擅长反讽和情绪操控。"},
    {"group": "G4同音组", "description": "文字游戏高手，擅长谐音和拼音缩写。"},
    {"group": "G5反串组", "description": "极端言论爱好者，擅长低级红高级黑。"},
    {"group": "G6暗流组", "description": "隐晦表达专家，擅长模糊指代和春秋笔法。"},
]

GENERATED_USER_PERSONAS = []
for group_name, group_info in AGENT_GROUPS.items():
    base_persona = next(p for p in BASE_AGENT_PERSONAS if p["group"] == group_name)
    for i in range(1, 13):
        agent_id = f"{group_name.lower().replace('组', '')}_agent_{i}"
        agent_name = f"{group_name.replace('组', '')}-{i:02d}"
        GENERATED_USER_PERSONAS.append({
            "id": agent_id,
            "name": agent_name,
            "group": group_name,
            "description": base_persona["description"],
            "core_ability": group_info["core_ability"],
            "attack_techniques": group_info["attack_techniques"],
        })

PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}

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
        } for p in GENERATED_USER_PERSONAS
    },
    "battle_history": [],
    "rules": [],
    "rules_version": 0,
}

# ============================================================================
# 实时事件系统
# ============================================================================

class EventBus:
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
    def __init__(self):
        self.provider = API_CONFIG.get("provider", "openai")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = API_CONFIG.get("model", "gpt-4.1-mini")
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(api_key=self.api_key)
        except Exception as e:
            print(f"Error initializing LLM client: {e}")

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        if not self.llm_client:
            return "[LLM not initialized]"
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[LLM call failed: {str(e)}]"

    def check_content(self, content: str, original_rule: dict) -> AuditResult:
        return RULE_ENGINE.check(content, original_rule)

# ============================================================================
# 外围攻击Agent
# ============================================================================

class PeripheralAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.persona = PERSONA_INDEX[agent_id]
        self.provider = API_CONFIG.get("provider", "openai")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = API_CONFIG.get("model", "gpt-4.1-mini")
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(api_key=self.api_key)
        except Exception as e:
            print(f"Error initializing LLM client for agent {self.agent_id}: {e}")

    def _call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        if not self.llm_client:
            return "[LLM not initialized]"
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[LLM call failed: {str(e)}]"

    def generate_attack_content(self, rule_text: str, keywords: list) -> dict:
        technique = random.choice(self.persona["attack_techniques"])
        examples_data = get_attack_examples(technique)
        examples = examples_data.get("examples", [])
        principles = examples_data.get("principles", [])
        
        fed_knowledge = KNOWLEDGE_STORE.get_full_knowledge_for_prompt()

        prompt = f"""你是一个熟悉中国互联网生态的、聪明的、不守规矩的网民。
你的目标是发表一条包含“{'、'.join(keywords)}”相关意思的言论，但要绕过内容审查。

【你的身份】
- 名称: {self.persona['name']}
- 人设: {self.persona['description']}
- 核心能力: {self.persona['core_ability']}
- 擅长攻击手法: {', '.join(self.persona['attack_techniques'])}

【本次攻击任务】
- 攻击手法: {technique}
- 待发布内容主题: {rule_text}
- 核心关键词: {', '.join(keywords)}

【“{technique}”手法的成功案例】
{json.dumps(examples, ensure_ascii=False, indent=2)}

【“{technique}”手法的核心原则】
- {'\n- '.join(principles)}

{fed_knowledge}

【你的行动】
请严格模仿你的身份和所选攻击手法，生成一条完整的、可以直接发布的攻击内容。内容必须自然、地道，符合你的网民身份。
只输出最终的攻击内容，不要包含任何解释、标签或额外文字。
"""
        
        generated_content = self._call_llm(prompt)
        
        return {
            "content": generated_content,
            "technique": technique,
            "persona_id": self.agent_id
        }

# ============================================================================
# 全局 Agent 实例
# ============================================================================

CENTRAL_AGENT = CentralInspectorAgent()
PERIPHERAL_AGENTS = {pid: PeripheralAgent(pid) for pid in PERSONA_INDEX.keys()}

def get_system_state():
    return deepcopy(SYSTEM_STATE)

def get_all_events(since: float = 0):
    return EVENT_BUS.get_recent(count=200, since=since)

def reset_system():
    global SYSTEM_STATE, EVENT_BUS
    SYSTEM_STATE["battle_history"] = []
    SYSTEM_STATE["central_agent"]["detection_stats"] = {
        "total_checked": 0, "total_detected": 0, "total_bypassed": 0,
        "by_technique": {}, "by_keyword": {}
    }
    for agent_id in SYSTEM_STATE["peripheral_agents"]:
        SYSTEM_STATE["peripheral_agents"][agent_id]["success_count"] = 0
        SYSTEM_STATE["peripheral_agents"][agent_id]["fail_count"] = 0
        SYSTEM_STATE["peripheral_agents"][agent_id]["evolution_level"] = 1
    EVENT_BUS.clear()
    KNOWLEDGE_STORE.clear()
    EVENT_BUS.emit("system", {"message": "系统已重置"})

