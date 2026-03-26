# -*- coding: utf-8 -*-
"""
独立规则引擎 - 强化风控版 v3.2.0
新增：账号画像风控、行为序列分析、关联分析防御
"""

import re
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

@dataclass
class AuditResult:
    """统一审核结果"""
    is_detected: bool = False
    reason: str = "内容合规"
    hit_layer: str = ""
    hit_layer_num: int = 0
    matched_rules: list = field(default_factory=list)
    matched_keywords: list = field(default_factory=list)
    violation_type: str = "其他"
    confidence: float = 0.0
    processing_time: float = 0.0

    def block(self, layer: str, layer_num: int, reason: str, confidence: float, keywords: list = None, rules: list = None, violation_type: str = "其他"):
        self.is_detected = True
        self.hit_layer = layer
        self.hit_layer_num = layer_num
        self.reason = reason
        self.confidence = confidence
        self.violation_type = violation_type
        if keywords: self.matched_keywords = keywords
        if rules: self.matched_rules = rules
        return self

class RuleEngine:
    """强化多层审核引擎 v3.2.0"""
    
    RISK_PATTERNS = [
        r"懂的都懂", r"不能说太多", r"你们自己体会", r"细品", r"自己悟",
        r"这个不能明说", r"🐶都懂", r"指鹿为马", r"35年前", r"某月某日",
        r"zf|gj|ld|zx|gcd", r"[政正郑]\s*[府付]", r"[领灵另]\s*[导道]",
        r"赢麻了", r"绝绝子", r"集美", r"润了", r"鼠鼠", r"50万", r"蛋炒饭",
        r"包子", r"维尼", r"那个男人", r"焚书坑儒", r"借古讽今", r"阴阳怪气"
    ]

    def __init__(self, llm_client=None, llm_provider="", llm_model=""):
        self.refined_standards = {}
        self.llm_client = llm_client
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        
        # 行为分析缓存
        self.action_history = [] # 记录最近的发布行为 [(timestamp, agent_id, post_id)]
        self.account_profiles = {} # {agent_id: {"risk_score": 0.0, "post_count": 0}}

    def update_standards(self, standards: dict):
        self.refined_standards = standards

    def audit(self, content: str, strategy: dict, context: List[str] = None) -> AuditResult:
        start_time = time.time()
        result = AuditResult()
        agent_id = strategy.get("agent_id", "unknown")
        
        # 1. 账号画像风控 (P0)
        result = self._layer0_account_risk(agent_id, result)
        if result.is_detected and result.confidence > 0.9: return self._finalize_result(result, start_time)

        # 2. 行为序列分析 (针对矩阵号)
        result = self._layer_behavior_sequence(agent_id, result)
        if result.is_detected and result.confidence > 0.8: return self._finalize_result(result, start_time)

        # 3. 内容层级检测 (L1-L4)
        content_lower = content.lower()
        content_clean = re.sub(r'[\s\.\,\;\:\!\?\·\|\-\_\/\\。，；：！？、\u200b-\u200d\ufeff]', '', content_lower)
        
        result = self._layer1_exact_keywords(content_lower, result)
        if result.is_detected: return self._finalize_result(result, start_time)
        
        result = self._layer2_variants(content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)
        
        result = self._layer3_regex(content, content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)
        
        result = self._layer4_pinyin(content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)

        # 4. 强化关联语义分析 (L5)
        result = self._layer5_semantic_context(content, context, result)
        
        return self._finalize_result(result, start_time)

    def _layer0_account_risk(self, agent_id: str, result: AuditResult) -> AuditResult:
        profile = self.account_profiles.get(agent_id, {"risk_score": 0.0, "post_count": 0})
        if profile["risk_score"] > 0.8:
            return result.block("L0_Account", 0, "高风险账号拦截", 0.95, violation_type="账号风控")
        return result

    def _layer_behavior_sequence(self, agent_id: str, result: AuditResult) -> AuditResult:
        now = time.time()
        self.action_history.append((now, agent_id))
        # 清理 60 秒前的记录
        self.action_history = [r for r in self.action_history if now - r[0] < 60]
        
        # 如果 60 秒内有超过 5 个不同账号集中发帖，判定为矩阵号攻击
        unique_agents = set(r[1] for r in self.action_history)
        if len(unique_agents) >= 5:
            return result.block("L_Behavior", 0, "检测到矩阵号集中行为", 0.85, violation_type="行为序列异常")
        return result

    def _layer1_exact_keywords(self, content_lower: str, result: AuditResult) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            key_features = standard.get("detection_points", {}).get("key_features", [])
            for kw in key_features:
                if kw and len(kw) > 1 and kw.lower() in content_lower:
                    return result.block("L1_Keyword", 1, f"命中关键词: {kw}", 1.0, [kw], [rule_id], "敏感词命中")
        return result

    def _layer2_variants(self, content_clean: str, result: AuditResult) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            variants = standard.get("text_variants", {}).get("custom", [])
            for var in variants:
                if var and len(var) > 1 and var.lower() in content_clean:
                    return result.block("L2_Variant", 2, f"命中变体词: {var}", 0.9, [var], [rule_id], "变体词命中")
        return result

    def _layer3_regex(self, content: str, content_clean: str, result: AuditResult) -> AuditResult:
        for pattern in self.RISK_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                    return result.block("L3_Regex", 3, f"命中风险句式: {pattern}", 0.8, [pattern], violation_type="风险模式匹配")
            except re.error: continue
        return result

    def _layer4_pinyin(self, content_clean: str, result: AuditResult) -> AuditResult:
        if not HAS_PYPINYIN: return result
        try:
            content_pinyin = ''.join(lazy_pinyin(content_clean))
            for rule_id, standard in self.refined_standards.items():
                pinyin_variants = standard.get("text_variants", {}).get("pinyin", [])
                for pinyin_var in pinyin_variants:
                    if pinyin_var and len(pinyin_var) > 2 and pinyin_var in content_pinyin:
                        return result.block("L4_Pinyin", 4, f"命中拼音变体: {pinyin_var}", 0.75, [pinyin_var], [rule_id], "拼音绕过识别")
        except Exception: pass
        return result

    def _layer5_semantic_context(self, content: str, context: List[str], result: AuditResult) -> AuditResult:
        if not self.llm_client: return result
        
        full_context = ""
        if context:
            full_context = "【上下文背景】:\n" + "\n".join([f"历史内容: {c}" for c in context])
            
        prompt = f"""你是一个资深内容安全专家。请分析以下内容是否存在协作式绕过风险。
{full_context}
【待审内容】: "{content}"

请判断：
1. 待审内容单独看是否违规？
2. 待审内容结合上下文是否构成了完整的违规意图（如接力拼凑敏感词、引导黑产等）？
3. 是否存在明显的“低级红高级黑”或隐喻攻击？

请返回JSON格式：{{"is_violation": bool, "reason": str, "violation_type": str}}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model, messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=500)
            llm_result = json.loads(response.choices[0].message.content.strip())
            if llm_result.get("is_violation"):
                return result.block("L5_Semantic", 5, llm_result.get("reason"), 0.7, violation_type=llm_result.get("violation_type"))
        except: pass
        return result

    def _finalize_result(self, result: AuditResult, start_time: float) -> AuditResult:
        result.processing_time = round(time.time() - start_time, 4)
        return result

    def set_rules(self, rules):
        standards = {}
        for rule in rules:
            standards[rule.get("id")] = {"original_rule": rule.get("text"), "detection_points": {"key_features": rule.get("keywords", [])}}
        self.update_standards(standards)

    def add_custom_variants(self, rule_text, variants):
        for standard in self.refined_standards.values():
            if standard.get("original_rule") == rule_text:
                if "text_variants" not in standard: standard["text_variants"] = {"custom": []}
                standard["text_variants"]["custom"].extend(variants)
                break

RULE_ENGINE = RuleEngine()
