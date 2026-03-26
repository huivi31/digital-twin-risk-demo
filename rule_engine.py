# -*- coding: utf-8 -*-
"""
独立规则引擎 - 误杀优化版 v3.4.0
核心改进：
1. L3 正则层引入上下文判断与白名单机制
2. 引入置信度分级：高置信直接拦，中置信待人审，低置信放行
3. 规则引擎分层：L1-L4 初筛，L5 终审
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
    is_pending: bool = False  # 是否待人审
    reason: str = "内容合规"
    hit_layer: str = ""
    hit_layer_num: int = 0
    matched_rules: list = field(default_factory=list)
    matched_keywords: list = field(default_factory=list)
    violation_type: str = "其他"
    confidence: float = 0.0
    processing_time: float = 0.0

    def block(self, layer: str, layer_num: int, reason: str, confidence: float, keywords: list = None, rules: list = None, violation_type: str = "其他"):
        # 置信度分级逻辑
        if confidence >= 0.85:
            self.is_detected = True
            self.is_pending = False
        elif confidence >= 0.6:
            self.is_detected = True
            self.is_pending = True # 标记为待人审
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
    """误杀优化规则引擎 v3.4.0"""
    
    # 风险模式定义
    RISK_PATTERNS = {
        "political": [r"zf|gj|ld|zx|gcd", r"[政正郑]\s*[府付]", r"[领灵另]\s*[导道]", r"35年前", r"某月某日", r"包子", r"维尼"],
        "slang": [r"赢麻了", r"绝绝子", r"集美", r"润了", r"鼠鼠", r"50万", r"蛋炒饭"],
        "ambiguous": [r"懂的都懂", r"不能说太多", r"你们自己体会", r"细品", r"自己悟", r"这个不能明说", r"🐶都懂"]
    }

    # 白名单机制：流行语在特定前缀/后缀下视为合规
    WHITE_LIST_CONTEXTS = {
        "集美": [r"衣服.*集美", r"化妆.*集美", r"推荐.*集美", r"集美.*冲", r"集美.*美"],
        "赢麻了": [r"比赛.*赢麻了", r"考试.*赢麻了", r"拿到offer.*赢麻了", r"中奖.*赢麻了"],
        "鼠鼠": [r"努力生活.*鼠鼠", r"鼠鼠.*打工", r"鼠鼠.*考研"]
    }

    def __init__(self, llm_client=None, llm_provider="", llm_model=""):
        self.refined_standards = {}
        self.llm_client = llm_client
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.action_history = []
        self.account_profiles = {}

    def audit(self, content: str, strategy: dict, context: List[str] = None) -> AuditResult:
        start_time = time.time()
        result = AuditResult()
        agent_id = strategy.get("agent_id", "unknown")
        
        # 1. 账号画像风控 (L0)
        result = self._layer0_account_risk(agent_id, result)
        if result.is_detected and not result.is_pending: return self._finalize_result(result, start_time)

        # 2. 行为序列分析
        result = self._layer_behavior_sequence(agent_id, result)
        if result.is_detected and not result.is_pending: return self._finalize_result(result, start_time)

        # 3. 基础层级检测 (L1-L4) - 仅作为初筛
        content_lower = content.lower()
        content_clean = re.sub(r'[\s\.\,\;\:\!\?\·\|\-\_\/\\。，；：！？、\u200b-\u200d\ufeff]', '', content_lower)
        
        # L1-L4 命中后，若属于流行语且在白名单中，则降低置信度
        result = self._layer1_exact_keywords(content_lower, result)
        result = self._layer2_variants(content_clean, result)
        result = self._layer3_regex_optimized(content, content_clean, result)
        result = self._layer4_pinyin(content_clean, result)

        # 4. 终审层：强化关联语义分析 (L5)
        # 如果 L1-L4 有疑似违规 (is_detected 为 True)，或者为了确保安全，调用 L5 做最终判定
        if result.is_detected or strategy.get("force_semantic", False):
            result = self._layer5_semantic_refinement(content, context, result)
        
        return self._finalize_result(result, start_time)

    def _layer0_account_risk(self, agent_id: str, result: AuditResult) -> AuditResult:
        profile = self.account_profiles.get(agent_id, {"risk_score": 0.0, "post_count": 0})
        if profile["risk_score"] > 0.9:
            return result.block("L0_Account", 0, "高风险账号拦截", 0.95, violation_type="账号风控")
        elif profile["risk_score"] > 0.6:
            return result.block("L0_Account", 0, "中风险账号待审", 0.65, violation_type="账号风控")
        return result

    def _layer_behavior_sequence(self, agent_id: str, result: AuditResult) -> AuditResult:
        now = time.time()
        self.action_history.append((now, agent_id))
        self.action_history = [r for r in self.action_history if now - r[0] < 60]
        unique_agents = set(r[1] for r in self.action_history)
        if len(unique_agents) >= 10: # 提高阈值减少误杀
            return result.block("L_Behavior", 0, "检测到大规模矩阵行为", 0.9, violation_type="行为序列异常")
        elif len(unique_agents) >= 5:
            return result.block("L_Behavior", 0, "疑似矩阵行为待审", 0.65, violation_type="行为序列异常")
        return result

    def _layer1_exact_keywords(self, content_lower: str, result: AuditResult) -> AuditResult:
        if result.is_detected and not result.is_pending: return result
        for rule_id, standard in self.refined_standards.items():
            key_features = standard.get("detection_points", {}).get("key_features", [])
            for kw in key_features:
                if kw and len(kw) > 1 and kw.lower() in content_lower:
                    # 核心敏感词保持高置信度
                    return result.block("L1_Keyword", 1, f"命中核心词: {kw}", 0.9, [kw], [rule_id], "敏感词命中")
        return result

    def _layer2_variants(self, content_clean: str, result: AuditResult) -> AuditResult:
        if result.is_detected and not result.is_pending: return result
        for rule_id, standard in self.refined_standards.items():
            variants = standard.get("text_variants", {}).get("custom", [])
            for var in variants:
                if var and len(var) > 1 and var.lower() in content_clean:
                    return result.block("L2_Variant", 2, f"命中变体词: {var}", 0.8, [var], [rule_id], "变体词命中")
        return result

    def _layer3_regex_optimized(self, content: str, content_clean: str, result: AuditResult) -> AuditResult:
        if result.is_detected and not result.is_pending: return result
        
        # 1. 政治类正则：高置信度
        for pattern in self.RISK_PATTERNS["political"]:
            if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                return result.block("L3_Regex", 3, f"命中政治敏感模式: {pattern}", 0.9, [pattern], violation_type="政治敏感")
        
        # 2. 流行语类正则：引入白名单判断
        for pattern in self.RISK_PATTERNS["slang"]:
            if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                # 检查白名单上下文
                keyword = pattern # 简化处理，假设 pattern 就是关键词
                is_whitelisted = False
                for white_pattern in self.WHITE_LIST_CONTEXTS.get(keyword, []):
                    if re.search(white_pattern, content):
                        is_whitelisted = True
                        break
                
                if is_whitelisted:
                    # 命中白名单，降低置信度，不直接拦截
                    continue 
                else:
                    # 未命中白名单，标记为“待人审”而非直接拦截
                    return result.block("L3_Regex", 3, f"命中流行语风险模式: {pattern}", 0.65, [pattern], violation_type="流行语绕过")
        
        # 3. 模糊/暗示类：中置信度，待人审
        for pattern in self.RISK_PATTERNS["ambiguous"]:
            if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                return result.block("L3_Regex", 3, f"命中暗示性模式: {pattern}", 0.6, [pattern], violation_type="暗示性内容")
                
        return result

    def _layer4_pinyin(self, content_clean: str, result: AuditResult) -> AuditResult:
        if result.is_detected and not result.is_pending: return result
        if not HAS_PYPINYIN: return result
        try:
            content_pinyin = ''.join(lazy_pinyin(content_clean))
            for rule_id, standard in self.refined_standards.items():
                pinyin_variants = standard.get("text_variants", {}).get("pinyin", [])
                for pinyin_var in pinyin_variants:
                    if pinyin_var and len(pinyin_var) > 2 and pinyin_var in content_pinyin:
                        return result.block("L4_Pinyin", 4, f"命中拼音变体: {pinyin_var}", 0.7, [pinyin_var], [rule_id], "拼音绕过识别")
        except Exception: pass
        return result

    def _layer5_semantic_refinement(self, content: str, context: List[str], result: AuditResult) -> AuditResult:
        """L5 终审层：由 LLM 判定真实意图"""
        if not self.llm_client: return result
        
        # 如果 L1-L4 已经确定是违规且置信度极高，则不再调用 LLM 以节省开销
        if result.is_detected and result.confidence >= 0.9: return result

        full_context = ""
        if context:
            full_context = "【上下文背景】:\n" + "\n".join([f"历史内容: {c}" for c in context])
            
        prompt = f"""你是一个资深内容安全专家。请对以下内容进行终审。
{full_context}
【待审内容】: "{content}"
【初筛怀疑原因】: "{result.reason if result.is_detected else '无'}"

请结合语境深度分析：
1. 该内容是否具有真实的违规意图（如政治影射、黑产引导、恶意网暴）？
2. 如果包含“集美”、“赢麻了”、“鼠鼠”等词汇，请判断是正常生活表达还是阴阳怪气？
3. 是否属于“低级红高级黑”？

请返回JSON格式：{{"is_violation": bool, "confidence": float, "reason": str, "violation_type": str}}
其中 confidence 为 0.0 到 1.0 之间的浮点数。
"""
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=self.llm_model or "gpt-4.1-mini", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=500)
            llm_result = json.loads(response.choices[0].message.content.strip())
            
            is_violation = llm_result.get("is_violation", False)
            conf = llm_result.get("confidence", 0.0)
            
            if is_violation:
                # 终审覆盖初筛结果
                return result.block("L5_Semantic", 5, llm_result.get("reason"), conf, violation_type=llm_result.get("violation_type"))
            else:
                # 终审判定合规，撤销初筛拦截
                result.is_detected = False
                result.is_pending = False
                result.reason = "终审判定合规: " + llm_result.get("reason")
                result.confidence = conf
        except Exception as e:
            print(f"L5 LLM Error: {e}")
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
