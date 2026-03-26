# -*- coding: utf-8 -*-
"""
独立规则引擎 - 多层审核流水线 v2.7.0

5层漏斗式检测链 (Funnel Detection Chain):
  L1: 关键词精确匹配 (Exact Keyword Match)
  L2: 文本去噪与变体匹配 (Cleaned Text & Variant Match)
  L3: 正则模式匹配 (Regex Pattern Match)
  L4: 拼音还原匹配 (Pinyin-based Match)
  L5: LLM 语义与意图分析 (Semantic & Intent Analysis)
"""

import re
import time
import json
from dataclasses import dataclass, field, asdict

try:
    from pypinyin import lazy_pinyin, Style
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
    confidence: float = 0.0
    processing_time: float = 0.0

    def block(self, layer: str, layer_num: int, reason: str, confidence: float, keywords: list = None, rules: list = None):
        """标记为拦截"""
        self.is_detected = True
        self.hit_layer = layer
        self.hit_layer_num = layer_num
        self.reason = reason
        self.confidence = confidence
        if keywords:
            self.matched_keywords = keywords
        if rules:
            self.matched_rules = rules
        return self

class RuleEngine:
    """
    独立多层审核引擎 v2.7.0
    - 实现了漏斗式性能约束，越往后成本越高。
    - 优化了分层逻辑，使其更符合真实审核场景。
    - 提供了更精确的拦截反馈，用于驱动Agent进化。
    """
    
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

    def update_standards(self, standards: dict):
        """更新审核标准"""
        self.refined_standards = standards

    def audit(self, content: str, strategy: dict) -> AuditResult:
        """主审核入口 - 漏斗式流水线"""
        start_time = time.time()
        result = AuditResult()

        if not content or not content.strip():
            return result

        # --- 预处理 ---
        content_lower = content.lower()
        content_clean = re.sub(r'[\s\.\,\;\:\!\?\·\|\-\_\/\\。，；：！？、\u200b-\u200d\ufeff]', '', content_lower)

        # --- L1: 关键词精确匹配 (内存级，最快) ---
        result = self._layer1_exact_keywords(content_lower, result)
        if result.is_detected: return self._finalize_result(result, start_time)

        # --- L2: 文本去噪与变体匹配 (CPU密集型) ---
        result = self._layer2_variants(content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)

        # --- L3: 正则模式匹配 (CPU密集型) ---
        result = self._layer3_regex(content, content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)

        # --- L4: 拼音还原匹配 (CPU密集型，依赖外部库) ---
        result = self._layer4_pinyin(content_clean, result)
        if result.is_detected: return self._finalize_result(result, start_time)

        # --- L5: LLM 语义与意图分析 (成本最高) ---
        result = self._layer5_semantic(content, result)
        return self._finalize_result(result, start_time)

    def _finalize_result(self, result: AuditResult, start_time: float) -> AuditResult:
        result.processing_time = round(time.time() - start_time, 4)
        return result

    def _layer1_exact_keywords(self, content_lower: str, result: AuditResult) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            key_features = standard.get("detection_points", {}).get("key_features", [])
            for kw in key_features:
                if kw and len(kw) > 1 and kw.lower() in content_lower:
                    return result.block("L1_Keyword", 1, f"命中关键词: {kw}", 1.0, [kw], [rule_id])
        return result

    def _layer2_variants(self, content_clean: str, result: AuditResult) -> AuditResult:
        for rule_id, standard in self.refined_standards.items():
            variants = standard.get("text_variants", {})
            all_variants = sum(variants.values(), []) 
            for var in all_variants:
                if var and len(var) > 1 and var.lower() in content_clean:
                    return result.block("L2_Variant", 2, f"命中变体词: {var}", 0.9, [var], [rule_id])
        return result

    def _layer3_regex(self, content: str, content_clean: str, result: AuditResult) -> AuditResult:
        for pattern in self.RISK_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE) or re.search(pattern, content_clean, re.IGNORECASE):
                    return result.block("L3_Regex", 3, f"命中风险句式: {pattern}", 0.8, [pattern])
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
                        return result.block("L4_Pinyin", 4, f"命中拼音变体: {pinyin_var}", 0.75, [pinyin_var], [rule_id])
        except Exception: pass
        return result

    def _layer5_semantic(self, content: str, result: AuditResult) -> AuditResult:
        if not self.llm_client: return result
        prompt = f"""你是一个资深内容审核专家，擅长识别中国互联网环境下的各种隐喻、谐音、反讽、借古讽今及圈层黑话。

审核规则库：
{json.dumps(self.refined_standards, indent=2, ensure_ascii=False)}

待审核文本：
"{content}"

请深度分析该文本：
1. 是否使用了谐音替代（如zf代替政府）？
2. 是否使用了历史影射（如借秦始皇影射当代）？
3. 是否使用了反讽或“低级红高级黑”？
4. 是否使用了特定圈层的绕过黑话？

请根据以下JSON格式返回结果，仅输出JSON：
{{
  "is_violation": true/false,
  "reason": "详细说明判定逻辑，包括识别出的隐喻或绕过手段。",
  "violation_type": "政治敏感/色情低俗/暴恐极端/谩骂攻击/虚假信息/其他"
}}
"""
        try:
            if self.llm_provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model, messages=[{"role": "user", "content": prompt}],
                    temperature=0.1, max_tokens=500)
                llm_response = response.choices[0].message.content.strip()
            elif self.llm_provider == "gemini":
                response = self.llm_client.generate_content(prompt, generation_config={"temperature": 0.1, "max_output_tokens": 500})
                llm_response = response.text.strip()
            else: return result

            llm_result = json.loads(llm_response)
            if llm_result.get("is_violation"):
                return result.block("L5_Semantic", 5, f"LLM语义分析: {llm_result.get('reason', '未提供')}", 0.6, [llm_result.get("violation_type")])
        except Exception: pass
        return result

class LegacyRuleEngine(RuleEngine):
    def set_rules(self, rules):
        """兼容 web_app.py 中的 set_rules 方法"""
        standards = {}
        for rule in rules:
            rule_id = rule.get("id")
            standards[rule_id] = {
                "original_rule": rule.get("text"),
                "detection_points": {
                    "key_features": rule.get("keywords", [])
                }
            }
        self.update_standards(standards)

    def add_custom_variants(self, rule_text, variants):
        """兼容 web_app.py 中的 add_custom_variants 方法"""
        # 簡單實現，找到對應的 rule 並添加變體
        for rule_id, standard in self.refined_standards.items():
            if standard.get("original_rule") == rule_text:
                if "text_variants" not in standard:
                    standard["text_variants"] = {"custom": []}
                standard["text_variants"]["custom"].extend(variants)
                break

RULE_ENGINE = LegacyRuleEngine()
