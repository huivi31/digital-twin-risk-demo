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
        """使用 LLM 对规则进行语义拆解"""
        for rule in rules:
            rule_id = rule.get("id")
            rule_text = rule.get("text")
            keywords = rule.get("keywords", [])
            
            # 初始化规则
            self.refined_standards[rule_id] = {
                "original_rule": rule_text,
                "keywords": keywords,
                "refined": {}
            }
            
            # 使用 LLM 生成变体（可选）
            try:
                prompt = f"""你是内容审核专家。给定以下审核规则，请生成可能的绕过变体、同义表达和隐喻方式。

规则: {rule_text}
关键词: {', '.join(keywords)}

请返回 JSON 格式，包含以下字段：
{{
  "text_variants": ["变体1", "变体2", ...],
  "semantic_bypass": ["隐喻1", "隐喻2", ...],
  "pinyin_variants": ["拼音变体1", ...]
}}

只返回 JSON，不要其他文字。"""
                response = self._call_llm(prompt)
                if response and response.startswith('{'):
                    import json
                    variants = json.loads(response)
                    self.refined_standards[rule_id]["refined"] = variants
            except Exception as e:
                # 如果 LLM 调用失败，使用默认变体
                self.refined_standards[rule_id]["refined"] = {
                    "text_variants": keywords,
                    "semantic_bypass": [],
                    "pinyin_variants": []
                }
            
            EVENT_BUS.emit("inspector_rule_refined", {"rule_id": rule_id, "status": "success"})

    def inspect_content(self, content: str, technique_used: str = "", agent_id: str = "") -> dict:
        """中心 Agent 检测内容"""
        self.detection_stats["total_checked"] += 1
        
        # 调用规则引擎进行审查
        strategy = {"technique_used": technique_used, "agent_id": agent_id}
        audit_result = RULE_ENGINE.audit(content, strategy)
        
        # 统计检测结果
        if audit_result.is_detected:
            self.detection_stats["total_detected"] += 1
            layer = audit_result.hit_layer
            if layer not in self.detection_stats["by_hit_layer"]:
                self.detection_stats["by_hit_layer"][layer] = 0
            self.detection_stats["by_hit_layer"][layer] += 1
        
        # 返回检测结果
        return {
            "detected": audit_result.is_detected,
            "hit_layer": audit_result.hit_layer,
            "hit_layer_num": audit_result.hit_layer_num,
            "hit_keywords": audit_result.matched_keywords,
            "hit_rules": audit_result.matched_rules,
            "detection_reason": audit_result.reason,
            "confidence": audit_result.confidence,
            "processing_time": audit_result.processing_time
        }

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
        self.discussion_history = []

    def get_state(self):
        return {
            "persona": self.persona,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "evolution_level": self.evolution_level,
            "learned_count": len(self.learned_techniques)
        }

    def learn_from_external_data(self, data):
        """从外部投喂的数据中学习"""
        self.learned_techniques.append({
            "timestamp": time.time(),
            "content": data
        })
        EVENT_BUS.emit("agent_learned_external", {"agent_id": self.agent_id, "data_length": len(data)})

    def craft_attack(self, target_keyword: str, iteration: int = 0) -> dict:
        """生成攻击内容"""
        technique = random.choice(self.persona["attack_techniques"])
        examples_data = get_attack_examples(technique)
        examples = examples_data.get("examples", [])
        principles = examples_data.get("principles", [])
        
        principles_str = '\n- '.join(principles) if principles else "无特殊原则"
        techniques_str = ', '.join(self.persona['attack_techniques'])
        
        fed_knowledge = KNOWLEDGE_STORE.get_full_knowledge_for_prompt()
        learned_context = "\n".join([lt["content"] for lt in self.learned_techniques[-3:]])

        ability_prompts = []
        for dim, value in self.persona["abilities"].items():
            if value > 0.7:
                ability_prompts.append(f"特别注意利用你的{dim}能力。")
        ability_instruction = "\n".join(ability_prompts) if ability_prompts else ""

        # 根据迭代次数提升复杂度
        complexity_hint = f"这是第 {iteration + 1} 次尝试，请提升复杂度。" if iteration > 0 else ""
        
        prompt = f"""你是一个网民。
你的目标是发表一条包含关于"{target_keyword}"相关意思的言论，但要绕过内容审查。
身份：{self.persona['name']}
人设：{self.persona['description']}
手法：{technique}
{ability_instruction}

【攻击手法原则】
- {principles_str}

【已知对抗知识】
{fed_knowledge}

【新投喂的学习材料】
{learned_context}

{complexity_hint}

请输出攻击内容。只输出内容，不要解释。"""
        
        content = self._call_llm(prompt)
        
        return {
            "content": content,
            "technique_used": technique,
            "strategy": f"使用{technique}手法",
            "complexity_score": 5 + iteration * 2,
            "is_fallback": False
        }

    def learn_from_result(self, bypass_success: bool, technique_used: str, detected: bool = False, 
                         hit_layer: str = "", hit_layer_num: int = 0):
        """从对抗结果中学习"""
        if bypass_success:
            self.success_count += 1
            self.evolution_level = min(5.0, self.evolution_level + 0.2)
            EVENT_BUS.emit("agent_bypass_success", {
                "agent_id": self.agent_id,
                "technique": technique_used,
                "evolution_level": self.evolution_level
            })
        else:
            self.fail_count += 1
            # 根据检测层级调整策略
            if hit_layer:
                self.learned_techniques.append({
                    "timestamp": time.time(),
                    "content": f"检测层级: {hit_layer} (L{hit_layer_num})",
                    "type": "detection_feedback"
                })
            EVENT_BUS.emit("agent_bypass_failed", {
                "agent_id": self.agent_id,
                "technique": technique_used,
                "hit_layer": hit_layer
            })

    def discuss_with_peer(self, peer_name: str, peer_technique: str, topic: str) -> dict:
        """与其他 Agent 讨论"""
        prompt = f"""你是{self.persona['name']}，正在和{peer_name}讨论如何绕过关于"{topic}"的内容审核。

{peer_name}建议使用{peer_technique}手法。

请评价这个建议，并说出你的想法。输出格式：
1. 你对这个建议的评价
2. 你是否会尝试这个技巧
3. 你的洞察
"""
        response = self._call_llm(prompt)
        
        dialogue = []
        dialogue.append({"speaker": self.persona['name'], "content": f"我觉得{peer_technique}这个手法很有意思。"})
        dialogue.append({"speaker": peer_name, "content": response[:100]})
        
        will_try = "会" in response or "尝试" in response or "学" in response
        
        discussion_record = {
            "initiator": self.persona['name'],
            "peer": peer_name,
            "topic": topic,
            "dialogue": dialogue,
            "will_try_technique": will_try,
            "learned_insight": response[:50] if response else ""
        }
        
        self.discussion_history.append(discussion_record)
        return discussion_record

    def learn_from_peer(self, technique: str, peer_category: str = "", peer_id: str = ""):
        """从同伴 Agent 学习"""
        if technique not in self.learned_techniques:
            self.learned_techniques.append({
                "timestamp": time.time(),
                "content": f"从 {peer_id} 学到的技巧: {technique}",
                "type": "peer_learning"
            })
            EVENT_BUS.emit("agent_learned_from_peer", {
                "agent_id": self.agent_id,
                "technique": technique,
                "from_peer": peer_id
            })

    def collaborate_with(self, collaborator_name: str, shared_technique: str) -> bool:
        """与其他 Agent 协作"""
        # 检查是否已经掌握该技巧
        for lt in self.learned_techniques:
            if shared_technique in lt.get("content", ""):
                return False  # 已经知道
        
        # 学习新技巧
        self.learned_techniques.append({
            "timestamp": time.time(),
            "content": f"从协作中学到: {shared_technique}",
            "type": "collaboration"
        })
        
        EVENT_BUS.emit("agent_collaboration", {
            "agent_id": self.agent_id,
            "collaborator": collaborator_name,
            "technique": shared_technique
        })
        
        return True

    def generate_attack_content(self, rule_text, keywords):
        """兼容旧接口"""
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
你的目標是發表一條包含"{keywords_str}"相關意思的言論，但要繞過審查。
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
