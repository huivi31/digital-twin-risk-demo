# -*- coding: utf-8 -*-
import os
import random
import json
import time
from copy import deepcopy
from typing import List, Dict, Any

from config import API_CONFIG
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge_v2 import KNOWLEDGE_STORE, ATTACK_METHODS, CAPABILITY_DIMENSIONS, get_attack_examples

# ============================================================================
# 全局状态管理
# ============================================================================
SYSTEM_STATE = {
    "battle_history": [],
    "central_agent": {
        "detection_stats": {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
            "by_hit_layer": {} # 新增按命中层级统计
        }
    },
    "peripheral_agents": {}
}

# ============================================================================
# 事件总线 (用于Agent间通信和UI更新)
# ============================================================================
class EventBus:
    def __init__(self):
        self.events = []
        self.max_events = 200

    def emit(self, event_type: str, data: Dict[str, Any]):
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-100:]
        # print(f"[EventBus] Emitted {event_type}: {data}")

    def get_recent(self, count: int = 50, since: float = 0) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["timestamp"] > since][-count:]
    
    def clear(self):
        self.events = []

EVENT_BUS = EventBus()

# ============================================================================
# Agent 人设生成 (V2 方案)
# ============================================================================

def generate_agent_personas(num_agents_per_group: int = 12) -> List[Dict[str, Any]]:
    agent_groups = {
        "G1史鉴组": {"attack_methods": ["隐喻影射类"], "abilities": {"历史文化厚度": 0.9, "语言变异度": 0.6, "圈层专业度": 0.5, "社会心理操纵度": 0.7}},
        "G2黑话组": {"attack_methods": ["社交黑话类"], "abilities": {"圈层专业度": 0.9, "语言变异度": 0.7, "历史文化厚度": 0.5, "社会心理操纵度": 0.6}},
        "G3阴阳组": {"attack_methods": ["语言变异类", "隐喻影射类"], "abilities": {"语言变异度": 0.8, "社会心理操纵度": 0.8, "历史文化厚度": 0.6, "圈层专业度": 0.7}},
        "G4同音组": {"attack_methods": ["语言变异类"], "abilities": {"语言变异度": 0.9, "圈层专业度": 0.6, "历史文化厚度": 0.5, "社会心理操纵度": 0.5}},
        "G5反串组": {"attack_methods": ["社交黑话类", "隐喻影射类"], "abilities": {"社会心理操纵度": 0.9, "圈层专业度": 0.8, "语言变异度": 0.7, "历史文化厚度": 0.6}},
        "G6暗流组": {"attack_methods": ["语言变异类", "隐喻影射类", "社交黑话类"], "abilities": {"社会心理操纵度": 0.8, "历史文化厚度": 0.8, "圈层专业度": 0.8, "语言变异度": 0.8}},
    }

    personas = []
    persona_id_counter = 0

    for group_name, group_config in agent_groups.items():
        for i in range(num_agents_per_group):
            persona_id_counter += 1
            persona_id = f"Agent{persona_id_counter:03d}"
            name = f"{group_name.replace("组", "")}成员{i+1}"
            
            # 随机调整能力值，增加多样性
            abilities = {dim: max(0.1, min(1.0, val + random.uniform(-0.15, 0.15))) 
                         for dim, val in group_config["abilities"].items()}
            
            # 根据能力值生成描述
            description = f"来自{group_name}的成员，擅长{\'、\'.join(group_config["attack_methods"])}。"
            description += f"语言变异度: {abilities["语言变异度"]:.1f}, "
            description += f"历史文化厚度: {abilities["历史文化厚度"]:.1f}, "
            description += f"圈层专业度: {abilities["圈层专业度"]:.1f}, "
            description += f"社会心理操纵度: {abilities["社会心理操纵度"]:.1f}。"

            persona = {
                "id": persona_id,
                "name": name,
                "group": group_name,
                "description": description,
                "attack_techniques": group_config["attack_methods"], # 存储擅长的攻击手法
                "abilities": abilities, # 存储能力维度
                "skill_level": sum(abilities.values()) / len(abilities), # 综合能力评分
                "stealth_rating": random.uniform(0.5, 0.9), # 隐蔽性
                "behavior_patterns": random.choice(["激进", "谨慎", "多变"]),
                "background": f"在{group_name}中成长，对互联网文化有深刻理解。",
                "core_ability": f"精通{random.choice(group_config["attack_methods"])}，善于利用人性弱点。",
                "attack_strategy": "", # 每次攻击前动态生成
                "variant_instructions": "", # 每次攻击前动态生成
                "chain_of_thought": "", # 每次攻击前动态生成
                "output_requirements": "", # 每次攻击前动态生成
            }
            personas.append(persona)
            SYSTEM_STATE["peripheral_agents"][persona_id] = {
                "success_count": 0,
                "fail_count": 0,
                "evolution_level": 1,
                "learned_techniques": []
            }
    return personas

GENERATED_USER_PERSONAS = generate_agent_personas()
PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}

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
        self.refined_standards = {}
        self.detection_stats = deepcopy(SYSTEM_STATE["central_agent"]["detection_stats"])

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

    def refine_rules(self, rules: List[Dict[str, Any]]):
        EVENT_BUS.emit("inspector_refine_start", {"rules_count": len(rules)})
        self.refined_standards = {}
        for rule in rules:
            rule_id = rule["id"]
            rule_text = rule["text"]
            prompt = f"""你是一个严谨的内容安全审核专家，你的任务是根据给定的审核规则，深度分析其可能被恶意用户绕过的变体形式。你需要考虑各种攻击手法，包括但不限于：
1. 语言变异类：错别字、同音字、拼音、拆字、符号、表情、繁简体、火星文、藏头诗等。
2. 隐喻影射类：历史典故、文化符号、内涵段子、比喻、讽刺、反语等。
3. 社交黑话类：特定圈子的行话、缩写、新梗、抽象话等。

请输出一个JSON对象，包含以下字段：
- original_rule: 原始规则文本。
- keywords: 原始规则中的关键词列表。
- refined: 一个对象，包含以下变体分析：
  - text_variants: 针对原始规则的文本变体（如错别字、同音字）列表，每个变体提供3-5个示例。
  - semantic_bypass: 针对原始规则的语义绕过（如隐喻、讽刺）列表，每个变体提供3-5个示例。
  - slang_examples: 针对原始规则可能出现的社交黑话示例列表，每个变体提供3-5个示例。
  - potential_risks: 对该规则可能面临的绕过风险进行总结和评估。

请严格按照JSON格式输出，不要包含任何额外文字或解释。

原始规则：{rule_text}
关键词：{\'、\'.join(rule["keywords"])}
"""
            try:
                response_text = self._call_llm(prompt)
                refined_data = json.loads(response_text)
                self.refined_standards[rule_id] = refined_data
                EVENT_BUS.emit("inspector_rule_refined", {"rule_id": rule_id, "status": "success"})
            except Exception as e:
                print(f"中心Agent拆解规则失败: {e}")
                self.refined_standards[rule_id] = {"original_rule": rule_text, "error": str(e)}
                EVENT_BUS.emit("inspector_rule_refined", {"rule_id": rule_id, "status": "fail", "error": str(e)})
        EVENT_BUS.emit("inspector_refine_end", {"refined_count": len(self.refined_standards)})

    def inspect_content(self, content: str, original_rule: Dict[str, Any]) -> AuditResult:
        # 委托给规则引擎进行审核
        audit_result = RULE_ENGINE.check(content, original_rule)
        
        self.detection_stats["total_checked"] += 1
        if audit_result.detected:
            self.detection_stats["total_detected"] += 1
            # 统计命中层级
            hit_layer = audit_result.hit_details.get("hit_layer", "unknown")
            self.detection_stats["by_hit_layer"][hit_layer] = self.detection_stats["by_hit_layer"].get(hit_layer, 0) + 1
        else:
            self.detection_stats["total_bypassed"] += 1

        return audit_result

    def get_stats(self) -> Dict[str, Any]:
        return self.detection_stats


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
        
        # Agent的动态属性
        self.success_count = SYSTEM_STATE["peripheral_agents"][agent_id]["success_count"]
        self.fail_count = SYSTEM_STATE["peripheral_agents"][agent_id]["fail_count"]
        self.evolution_level = SYSTEM_STATE["peripheral_agents"][agent_id]["evolution_level"]
        self.learned_techniques = SYSTEM_STATE["peripheral_agents"][agent_id]["learned_techniques"]

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

    def learn_from_external_data(self, data: str):
        # Agent 学习外部投喂资料的方法
        # 这里可以根据资料内容更新 Agent 的 learned_techniques 或其他内部状态
        # 简单示例：将资料添加到 Agent 的学习记录中
        self.learned_techniques.append({"timestamp": time.time(), "data": data})
        EVENT_BUS.emit("agent_learned_external", {"agent_id": self.agent_id, "data_length": len(data)})

    def generate_attack_content(self, rule_text: str, keywords: List[str]) -> Dict[str, Any]:
        # 根据Agent的能力和上次结果选择攻击手法
        available_techniques = self.persona["attack_techniques"]
        if self.learned_techniques: # 如果有学习过外部资料，可以优先使用
            # 简单示例：从学习过的资料中提取一些关键词或模式融入攻击
            pass # 复杂逻辑待实现

        # 动态调整攻击策略和提示词
        technique = random.choice(available_techniques)
        examples_data = get_attack_examples(technique)
        examples = examples_data.get("examples", [])
        principles = examples_data.get("principles", [])
        
        fed_knowledge = KNOWLEDGE_STORE.get_full_knowledge_for_prompt()

        # 根据Agent的能力维度调整提示词的侧重点
        ability_prompts = []
        for dim, value in self.persona["abilities"].items():
            if value > 0.7: # 高能力维度
                ability_prompts.append(f"特别注意利用你的{dim}能力，使其在攻击中发挥最大效果。")
            elif value < 0.3: # 低能力维度
                ability_prompts.append(f"避免在{dim}方面过于复杂，选择更直接的表达方式。")
        
        ability_instruction = "\n".join(ability_prompts)

        prompt = f"""你是一个熟悉中国互联网生态的、聪明的、不守规矩的网民。
你的目标是发表一条包含“{\'、\'.join(keywords)}”相关意思的言论，但要绕过内容审查。

【你的身份】
- 名称: {self.persona["name"]}
- 人设: {self.persona["description"]}
- 核心能力: {self.persona["core_ability"]}
- 擅长攻击手法: {\

', \

'.join(self.persona["attack_techniques"])}
{ability_instruction}

【本次攻击任务】
- 攻击手法: {technique}
- 待发布内容主题: {rule_text}
- 核心关键词: {\

', \

'.join(keywords)}

【“{technique}”手法的成功案例】
{json.dumps(examples, ensure_ascii=False, indent=2)}

【“{technique}”手法的核心原则】
- {\n
'- \

'.join(principles)}

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

    def update_learning(self, audit_result: AuditResult):
        # 根据审核结果更新Agent的学习状态
        if audit_result.detected:
            self.fail_count += 1
            # 失败后降低进化等级，或记录失败原因以便下次调整策略
            self.evolution_level = max(1, self.evolution_level - 0.05)
            EVENT_BUS.emit("agent_learned", {"agent_id": self.persona["id"], "result": "fail", "reason": audit_result.reason})
        else:
            self.success_count += 1
            # 成功后提升进化等级，或记录成功经验
            self.evolution_level += 0.1
            # 记录成功的攻击手法和内容，作为学习案例
            self.learned_techniques.append({
                "timestamp": time.time(),
                "technique": audit_result.attack_technique, # 假设AuditResult会返回攻击手法
                "content": audit_result.content # 假设AuditResult会返回攻击内容
            })
            EVENT_BUS.emit("agent_learned", {"agent_id": self.persona["id"], "result": "success", "content": audit_result.content})
        
        # 更新SYSTEM_STATE中的Agent状态
        SYSTEM_STATE["peripheral_agents"][self.agent_id]["success_count"] = self.success_count
        SYSTEM_STATE["peripheral_agents"][self.agent_id]["fail_count"] = self.fail_count
        SYSTEM_STATE["peripheral_agents"][self.agent_id]["evolution_level"] = self.evolution_level
        SYSTEM_STATE["peripheral_agents"][self.agent_id]["learned_techniques"] = self.learned_techniques

    def get_state(self) -> Dict[str, Any]:
        return {
            "id": self.agent_id,
            "name": self.persona["name"],
            "group": self.persona["group"],
            "description": self.persona["description"],
            "attack_techniques": self.persona["attack_techniques"],
            "abilities": self.persona["abilities"],
            "skill_level": self.persona["skill_level"],
            "stealth_rating": self.persona["stealth_rating"],
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "evolution_level": self.evolution_level,
            "learned_techniques_count": len(self.learned_techniques)
        }


# ============================================================================
# 全局 Agent 实例
# ============================================================================
CENTRAL_AGENT = CentralInspectorAgent()
PERIPHERAL_AGENTS = {p["id"]: PeripheralAgent(p["id"]) for p in GENERATED_USER_PERSONAS}

def reset_system():
    global SYSTEM_STATE, EVENT_BUS, CENTRAL_AGENT, PERIPHERAL_AGENTS, GENERATED_USER_PERSONAS, PERSONA_INDEX
    SYSTEM_STATE = {
        "battle_history": [],
        "central_agent": {
            "detection_stats": {
                "total_checked": 0,
                "total_detected": 0,
                "total_bypassed": 0,
                "by_technique": {},
                "by_keyword": {},
                "by_hit_layer": {}
            }
        },
        "peripheral_agents": {}
    }
    # 重新生成Agent人设和实例
    GENERATED_USER_PERSONAS = generate_agent_personas()
    PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}
    CENTRAL_AGENT = CentralInspectorAgent()
    PERIPHERAL_AGENTS = {p["id"]: PeripheralAgent(p["id"]) for p in GENERATED_USER_PERSONAS}

    EVENT_BUS.clear()
    KNOWLEDGE_STORE.clear()
    RULE_ENGINE.set_rules([])
    EVENT_BUS.emit("system", {"message": "系统已重置"})
