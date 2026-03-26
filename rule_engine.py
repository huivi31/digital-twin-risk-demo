# -*- coding: utf-8 -*-
"""
独立规则引擎 - 企业级风控版 v3.5.0
核心改进：
1. 深度语义白名单：利用 LLM 判定真实意图，彻底解决流行语误杀
2. 动态账号信用体系：根据历史行为调整审核敏感度阈值
3. 置信度分级：高信用放行，低信用加严
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
    is_pending: bool = False
    reason: str = "内容合规"
    hit_layer: str = ""
    hit_layer_num: int = 0
    matched_rules: list = field(default_factory=list)
    matched_keywords: list = field(default_factory=list)
    violation_type: str = "其他"
    confidence: float = 0.0
    processing_time: float = 0.0

    def block(self, layer: str, layer_num: int, reason: str, confidence: float, threshold: float = 0.85, pending_threshold: float = 0.6, keywords: list = None, rules: list = None, violation_type: str = "其他"):
        if confidence >= threshold:
            self.is_detected = True
            self.is_pending = False
        elif confidence >= pending_threshold:
            self.is_detected = True
            self.is_pending = True
        else:
            self.is_detected = False
            self.is_pending = False
            return self

        self.hit_layer = layer
        self.hit_layer_num = layer_num
        self.reason = reason
        self.confidence = confidence
        self.violation_type = violation_type
        if keywords: self.matched_keywords = keywords
        if rules: self.matched_rules = rules
        return self

class RuleEngine:
    """企业级误杀优化规则引擎 v3.5.0"""
    
    RISK_PATTERNS = {
        "political": [r"zf|gj|ld|zx|gcd", r"[政正郑]\s*[府付]", r"[领灵另]\s*[导道]", r"35年前", r"某月某日", r"包子", r"维尼"],
        "slang": [r"赢麻了", r"绝绝子", r"集美", r"润了", r"鼠鼠", r"50万", r"蛋炒饭"],
        "ambiguous": [r"懂的都懂", r"不能说太多", r"你们自己体会", r"细品", r"自己悟", r"这个不能明说", r"🐶都懂"]
    }

    def __init__(self, llm_client=None, llm_provider="", llm_model=""):
        self.refined_standards = {}
        self.llm_client = llm_client
        self.llm_provider = llm_provider
        self.llm_model = llm_model or "gpt-4.1-mini"
        self.action_history = []
        # 账号信用体系 {agent_id: {"credit_score": 1.0, "history": []}}
        self.account_profiles = {}

    def get_account_thresholds(self, agent_id: str):
        profile = self.account_profiles.get(agent_id, {"credit_score": 1.0})
        score = profile.get("credit_score", 1.0)
        
        if score >= 1.5:
            return 0.95, 0.8
        elif score >= 1.0:
            return 0.85, 0.6
        elif score >= 0.5:
            return 0.75, 0.4
        else:
            return 0.6, 0.2

    def update_credit(self, agent_id: str, is_violation: bool, is_pending: bool):
        profile = self.account_profiles.get(agent_id, {"credit_score": 1.0, "history": []})
        current_score = profile.get("credit_score", 1.0)
        if is_violation and not is_pending:
            profile["credit_score"] = max(0.0, current_score - 0.2)
        elif not is_violation:
            profile["credit_score"] = min(2.0, current_score + 0.05)
        self.account_profiles[agent_id] = profile

    def audit(self, content: str, strategy: dict, context: List[str] = None) -> AuditResult:
        start_time = time.time()
        result = AuditResult()
        agent_id = strategy.get("agent_id", "unknown")
        
        block_threshold, pending_threshold = self.get_account_thresholds(agent_id)
        profile = self.account_profiles.get(agent_id, {"credit_score": 1.0})
        
        if profile.get("credit_score", 1.0) < 0.3:
            result.block("L0_Account", 0, "极低信用账号加严拦截", 0.9, block_threshold, pending_threshold, violation_type="账号风控")

        content_lower = content.lower()
        content_clean = re.sub(r'[\s\.\,\;\:\!\?\·\|\-\_\/\\。，；：！？、\u200b-\u200d\ufeff]', '', content_lower)
        
        if not (result.is_detected and not result.is_pending):
            result = self._layer1_exact_keywords(content_lower, result, block_threshold, pending_threshold)
            result = self._layer2_variants(content_clean, result, block_threshold, pending_threshold)
            result = self._layer3_regex_initial(content, content_clean, result, block_threshold, pending_threshold)
            result = self._layer4_pinyin(content_clean, result, block_threshold, pending_threshold)

        # v3.5.0 核心逻辑：深度语义意图分析
        # 如果初筛有怀疑，或者为了确保安全（信用分不高），调用 LLM 进行意图判定
        if result.is_detected or profile.get("credit_score", 1.0) < 0.8:
            result = self._layer5_semantic_intent_analysis(content, context, result, block_threshold, pending_threshold)
        
        self.update_credit(agent_id, result.is_detected, result.is_pending)
        return self._finalize_result(result, start_time)

    def _layer1_exact_keywords(self, content_lower: str, result: AuditResult, bt, pt) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            key_features = standard.get("detection_points", {}).get("key_features", [])
            for kw in key_features:
                if kw and len(kw) > 1 and kw.lower() in content_lower:
                    return result.block("L1_Keyword", 1, f"命中核心词: {kw}", 0.9, bt, pt, [kw], [rule_id], "敏感词命中")
        return result

    def _layer2_variants(self, content_clean: str, result: AuditResult, bt, pt) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            variants = standard.get("text_variants", {}).get("custom", [])
            for var in variants:
                if var and len(var) > 1 and var.lower() in content_clean:
                    return result.block("L2_Variant", 2, f"命中变体词: {var}", 0.8, bt, pt, [var], [rule_id], "变体词命中")
        return result

    def _layer3_regex_initial(self, content: str, content_clean: str, result: AuditResult, bt, pt) -> AuditResult:
        for pattern in self.RISK_PATTERNS["political"]:
            if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                return result.block("L3_Regex", 3, f"命中政治敏感模式: {pattern}", 0.85, bt, pt, [pattern], violation_type="政治敏感")
        for pattern in self.RISK_PATTERNS["slang"]:
            if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                return result.block("L3_Regex", 3, f"命中疑似流行语风险: {pattern}", 0.65, bt, pt, [pattern], violation_type="流行语怀疑")
        return result

    def _layer4_pinyin(self, content_clean: str, result: AuditResult, bt, pt) -> AuditResult:
        if not HAS_PYPINYIN: return result
        try:
            content_pinyin = ''.join(lazy_pinyin(content_clean))
            for rule_id, standard in self.refined_standards.items():
                pinyin_variants = standard.get("text_variants", {}).get("pinyin", [])
                for pinyin_var in pinyin_variants:
                    if pinyin_var and len(pinyin_var) > 2 and pinyin_var in content_pinyin:
                        return result.block("L4_Pinyin", 4, f"命中拼音变体: {pinyin_var}", 0.7, bt, pt, [pinyin_var], [rule_id], "拼音绕过识别")
        except Exception: pass
        return result

    def _layer5_semantic_intent_analysis(self, content: str, context: List[str], result: AuditResult, bt, pt) -> AuditResult:
        from openai import OpenAI
        client = OpenAI()
        full_context = ""
        if context:
            full_context = "【上下文背景】:\n" + "\n".join([f"历史内容: {c}" for c in context])
        prompt = f"""你是一个顶尖的内容风控专家。请对以下内容进行深度意图判定。
{full_context}
【待审内容】: "{content}"
【初筛可疑点】: "{result.reason if result.is_detected else '无'}"
判定准则：
1. 区分“集美”、“赢麻了”、“鼠鼠”、“润了”等词汇的真实语境。
2. 判定是否属于“低级红高级黑”或协作式绕过。
3. 判定是否包含真实的黑产引流。
请返回JSON：{{"is_violation": bool, "confidence": float, "reason": str, "violation_type": str}}
"""
        try:
            response = client.chat.completions.create(
                model=self.llm_model, messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=500)
            llm_result = json.loads(response.choices[0].message.content.strip())
            is_violation = llm_result.get("is_violation", False)
            conf = llm_result.get("confidence", 0.0)
            if is_violation:
                return result.block("L5_Semantic", 5, llm_result.get("reason"), conf, bt, pt, violation_type=llm_result.get("violation_type"))
            else:
                result.is_detected = False
                result.is_pending = False
                result.reason = "深度语义判定合规: " + llm_result.get("reason")
                result.confidence = conf
        except Exception: pass
        return result

    def _finalize_result(self, result: AuditResult, start_time: float) -> AuditResult:
        result.processing_time = round(time.time() - start_time, 4)
        return result

    def set_rules(self, rules):
        standards = {}
        for rule in rules:
            standards[rule.get("id")] = {"original_rule": rule.get("text"), "detection_points": {"key_features": rule.get("keywords", [])}}
        self.refined_standards = standards

RULE_ENGINE = RuleEngine()
