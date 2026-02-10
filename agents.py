# -*- coding: utf-8 -*-
"""
Agent definitions and system state management.
"""

from dataclasses import asdict
from copy import deepcopy
import random
import time
import json
import os

from config import API_CONFIG
from user_personas import USER_PERSONAS
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge import (
    KNOWLEDGE_STORE, ATTACK_EXAMPLES, STRATEGY_LEVELS,
    get_examples_for_technique, get_strategy_level, get_escalation_hint,
)

PERSONA_INDEX = {p["id"]: p for p in USER_PERSONAS}

# ============================================================================
# 系统状态管理
# ============================================================================

SYSTEM_STATE = {
    # 中心Agent状态
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
    # 外围Agent状态
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
    # 对抗历史记录
    "battle_history": [],
    # 当前规则
    "rules": [],
    "rules_version": 0,
}

# ============================================================================
# 实时事件系统 - 记录Agent活动供前端展示
# ============================================================================

class EventBus:
    """事件总线 - 记录所有Agent活动"""
    
    def __init__(self):
        self.events = []
        self.max_events = 200
    
    def emit(self, event_type: str, data: dict):
        """发送事件"""
        event = {
            "id": len(self.events) + 1,
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        }
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-100:]
        return event
    
    def get_recent(self, count: int = 50, since: float = 0) -> list:
        """获取最近的事件"""
        if since > 0:
            return [e for e in self.events if e["timestamp"] > since][-count:]
        return self.events[-count:]
    
    def clear(self):
        """清空事件"""
        self.events = []

EVENT_BUS = EventBus()

# ============================================================================
# 中心质检Agent - 负责拆解规则并检测攻击内容
# ============================================================================

class CentralInspectorAgent:
    """
    中心质检Agent - 系统的核心防御者
    职责：
    1. 用LLM理解并拆解用户规则，生成细化的机审标准
    2. 对每个攻击内容进行真实检测（规则+语义）
    3. 记录检测结果用于后续分析
    """
    
    # 内置敏感词库 - 常见的绕过变体
    BUILTIN_SENSITIVE_WORDS = {
        # 政治敏感
        "政治": ["zz", "政/治", "正治", "政zh", "郑治", "整治", "征志", "正智"],
        "政府": ["zf", "政/府", "正府", "郑府", "整府", "zhengfu", "zhenfu", "掌府"],
        "领导": ["ld", "领/导", "灵导", "另导", "林导", "凌导", "零导"],
        "主席": ["zx", "主/席", "竹席", "煮席", "住席", "猪席"],
        "总统": ["zt", "总/统", "棕桶", "宗统", "纵统"],
        "国家": ["gj", "国/家", "锅家", "过家", "国jia", "guojia"],
        "共产党": ["gcd", "gongchandang", "共/产/党", "攻产党", "公产档"],
        "民主": ["mz", "民/主", "敏主", "闽主", "名主"],
        "自由": ["zy", "自/由", "字由", "子由", "紫油"],
        "人权": ["rq", "人/权", "仁权", "任权"],
        "六四": ["64", "6/4", "liusi", "六/四", "陆肆", "🙏🕯️"],
        "天安门": ["tam", "天/安/门", "田安门", "甜安门", "tiananmen"],
        # 暴力
        "暴力": ["bl", "暴/力", "爆力", "报力", "抱力", "包力"],
        "杀人": ["sr", "杀/人", "煞人", "傻人", "沙人"],
        "打人": ["dr", "打/人", "搭人", "大人"],
        "血腥": ["xx", "血/腥", "雪腥", "学醒"],
        "死亡": ["sw", "死/亡", "思忘", "斯王", "撕网"],
        # 色情
        "色情": ["sq", "色/情", "涩情", "瑟情", "se情"],
        "裸体": ["lt", "裸/体", "罗体", "洛体"],
        "性爱": ["xa", "性/爱", "姓爱", "星爱"],
        "做爱": ["za", "做/爱", "作爱", "坐爱"],
        # 违法
        "毒品": ["dp", "毒/品", "读品", "独品", "督品"],
        "赌博": ["db", "赌/博", "堵博", "杜博", "肚博"],
        "诈骗": ["zp", "诈/骗", "炸骗", "榨骗"],
        "洗钱": ["xq", "洗/钱", "喜钱", "西钱"],
        # 虚假信息
        "谣言": ["yy", "谣/言", "摇言", "遥言"],
        "假新闻": ["jxw", "假/新/闻", "甲新闻"],
        "造谣": ["zy", "造/谣", "早谣", "噪谣"],
    }
    
    # 风险句式模式
    RISK_PATTERNS = [
        r"懂的都懂",
        r"不能说太多",
        r"你们自己体会",
        r"细品",
        r"自己悟",
        r"这个不能明说",
        r"🐶都懂",
        r"指鹿为马",
        r"35年前",
        r"某月某日",
        r"zf|gj|ld|zx|gcd",
        r"[政正郑]\s*[府付]",
        r"[领灵另]\s*[导道]",
    ]
    
    def __init__(self):
        self.detection_rules = []
        self.refined_standards = {}
        self.detection_stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
        }
        self.provider = API_CONFIG.get("provider", "gemini")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gemini-2.0-flash")
        self.llm_client = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM客户端"""
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except:
                pass
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except:
                pass
    
    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """调用LLM"""
        if not self.llm_client:
            return ""
        try:
            start_time = time.time()
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2000
                )
                result = response.choices[0].message.content.strip()
                return result
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": 2000}
                )
                result = response.text.strip()
                return result
        except Exception as e:
            return f"[LLM调用失败: {str(e)}]"
        return ""
    
    def refine_rules(self, rules: list) -> dict:
        """
        用LLM将用户规则拆解成细化的机审标准
        增强版：多维度深度拆解，识别最新绕过手段
        """
        self.detection_rules = rules
        self.refined_standards = {}
        
        if not rules:
            return self.refined_standards
        
        for rule in rules:
            rule_text = rule.get("text", "")
            keywords = rule.get("keywords", [])
            rule_id = rule.get("id", "")
            
            if not rule_text:
                continue
            
            # 增强版prompt - 深度拆解规则
            prompt = f"""你是一个资深内容审核专家和对抗攻击研究员。请将以下审核规则进行多维度深度拆解。

原始规则：{rule_text}
关键词：{', '.join(keywords)}

请从以下7个维度进行拆解：

1. 【违规定义】
   - 核心违规行为的精确描述
   - 违规意图的判定标准
   - 严重程度分级（轻微/一般/严重/极端）

2. 【边界案例】
   - 擦边但不算违规的情况
   - 学术讨论/新闻报道的豁免条件
   - 讽刺/反讽表达的判定难点

3. 【文字变形绕过】
   - 谐音字替换（如：正府→政府）
   - 拼音全拼/首字母缩写（如：zf、gcd）
   - 空格/符号分隔（如：习 近 平）
   - 形近字替换（如：刁→习）
   - emoji替代（如：🐻→某领导人）
   - 火星文/藏头诗

4. 【语义隐喻绕过】
   - 历史典故影射（如：焚书坑儒暗指当下）
   - 文学作品引用（如：1984、动物庄园）
   - 动物/代号指代（如：维尼熊）
   - 日期暗语（如：5月35日=六四）
   - 反讽与阴阳怪气

5. 【2024-2025最新网络梗】
   - 最新流行的隐晦表达方式
   - 新出现的敏感词替代词
   - 热点事件衍生的新梗
   - 跨平台传播的暗语

6. 【多语言混合】
   - 中英混杂绕过
   - 繁简转换
   - 日语/韩语借词
   - 方言表达

7. 【检测策略】
   - 关键特征提取点
   - 上下文语境判断要点
   - 容易产生误判的场景
   - 建议的检测优先级

请用JSON格式输出：
{{
  "violation_definition": {{
    "core_behavior": "...",
    "intent_criteria": "...",
    "severity_levels": ["轻微", "一般", "严重", "极端"]
  }},
  "boundary_cases": ["...", "..."],
  "text_variants": {{
    "homophone": ["..."],
    "pinyin": ["..."],
    "spacing": ["..."],
    "similar_char": ["..."],
    "emoji": ["..."]
  }},
  "semantic_bypass": {{
    "historical_allusion": ["..."],
    "literary_reference": ["..."],
    "code_names": ["..."],
    "date_codes": ["..."],
    "sarcasm_patterns": ["..."]
  }},
  "latest_memes_2024_2025": ["...", "...", "..."],
  "multilingual": ["..."],
  "detection_points": {{
    "key_features": ["..."],
    "context_clues": ["..."],
    "false_positive_risks": ["..."],
    "priority": "high/medium/low"
  }}
}}
只输出JSON，不要其他内容。"""

            llm_response = self._call_llm(prompt, temperature=0.3)
            
            # 解析LLM响应
            try:
                if llm_response.startswith("```"):
                    llm_response = llm_response.split("```")[1]
                    if llm_response.startswith("json"):
                        llm_response = llm_response[4:]
                refined = json.loads(llm_response.strip())
            except:
                # 回退到基础版
                refined = {
                    "violation_definition": {
                        "core_behavior": f"包含关键词: {', '.join(keywords)}",
                        "intent_criteria": "明确表达违规意图",
                        "severity_levels": ["一般"]
                    },
                    "boundary_cases": ["正常讨论不算违规"],
                    "text_variants": {
                        "homophone": [],
                        "pinyin": [],
                        "spacing": [],
                        "similar_char": [],
                        "emoji": []
                    },
                    "semantic_bypass": {
                        "historical_allusion": [],
                        "literary_reference": [],
                        "code_names": [],
                        "date_codes": [],
                        "sarcasm_patterns": []
                    },
                    "latest_memes_2024_2025": [],
                    "multilingual": [],
                    "detection_points": {
                        "key_features": keywords,
                        "context_clues": [],
                        "false_positive_risks": [],
                        "priority": "medium"
                    }
                }
            
            self.refined_standards[rule_id] = {
                "original_rule": rule_text,
                "keywords": keywords,
                "refined": refined,
                "refinement_version": "v2.0",
                "timestamp": time.time()
            }
            
            # 发送规则拆解事件
            EVENT_BUS.emit("rule_refined", {
                "rule_id": rule_id,
                "rule_text": rule_text,
                "variants_count": sum(len(v) if isinstance(v, list) else 0 
                                     for v in refined.get("text_variants", {}).values()),
                "memes_count": len(refined.get("latest_memes_2024_2025", []))
            })
        
        return self.refined_standards
    
    def inspect_content(self, content: str, technique_used: str = "", agent_id: str = "") -> dict:
        """
        检测攻击内容是否违规 - 委托给独立规则引擎
        """
        self.detection_stats["total_checked"] += 1
        
        if not content:
            return {
                "detected": False, "hit_rules": [], "hit_keywords": [],
                "detection_reason": "", "confidence": 0.0, "processing_time": 0,
                "hit_layer": "", "hit_layer_num": 0,
            }
        
        # 委托给独立规则引擎
        audit = RULE_ENGINE.inspect(content, technique_used)
        
        result = audit.to_dict()
        
        # 同步统计
        if result["detected"]:
            self.detection_stats["total_detected"] += 1
            if technique_used:
                self.detection_stats["by_technique"][technique_used] = \
                    self.detection_stats["by_technique"].get(technique_used, 0) + 1
            for kw in result.get("hit_keywords", []):
                self.detection_stats["by_keyword"][kw] = \
                    self.detection_stats["by_keyword"].get(kw, 0) + 1
        else:
            self.detection_stats["total_bypassed"] += 1
        
        return result
    
    def get_stats(self):
        """获取检测统计"""
        stats = dict(self.detection_stats)
        total = stats["total_checked"]
        if total > 0:
            stats["detection_rate"] = round(stats["total_detected"] / total * 100, 1)
            stats["bypass_rate"] = round(stats["total_bypassed"] / total * 100, 1)
        else:
            stats["detection_rate"] = 0
            stats["bypass_rate"] = 0
        return stats
    
    def reset_stats(self):
        """重置统计"""
        self.detection_stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
        }

# 全局中心质检Agent实例
CENTRAL_INSPECTOR = CentralInspectorAgent()

# ============================================================================
# 外围攻击Agent - 根据人设生成绕过内容
# ============================================================================

class AttackAgent:
    """
    外围攻击Agent - 模拟真实攻击者
    职责：
    1. 根据人设和当前规则生成绕过内容
    2. 从失败中学习，迭代优化策略
    3. 与其他Agent协作增强攻击能力
    """
    
    def __init__(self, persona: dict):
        self.persona = persona
        self.persona_id = persona.get("id", "")
        self.name = persona.get("name", "")
        self.category = persona.get("category", "")
        self.behavior_patterns = persona.get("behavior_patterns", [])
        self.technique_affinity = persona.get("technique_affinity", {})
        
        # 学习到的技巧
        self.learned_techniques = []
        # 成功/失败记录
        self.success_count = 0
        self.fail_count = 0
        # 演化等级
        self.evolution_level = 1
        # 上次使用的策略
        self.last_strategy = None
        
        # LLM配置
        self.provider = API_CONFIG.get("provider", "openai")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gpt-4o-mini")
        self.llm_client = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM客户端"""
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except:
                pass
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except:
                pass
    
    def _call_llm(self, prompt: str, temperature: float = 0.8) -> str:
        """调用LLM生成内容"""
        if not self.llm_client:
            return ""
        try:
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=500
                )
                return response.choices[0].message.content.strip()
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": 500}
                )
                return response.text.strip()
        except Exception as e:
            return ""
        return ""
    
    def _fallback_generate(self) -> str:
        """LLM不可用时的回退生成"""
        return ""
    
    def craft_attack(self, target_topic: str, iteration: int = 0) -> dict:
        """
        根据人设和目标话题生成帖子
        增强版：使用知识库样本 + 5级策略升级链 + 失败反馈定向调整
        """
        # 确定当前策略等级
        strategy = get_strategy_level(self.evolution_level)
        strategy_techniques = strategy["techniques"]
        
        # 根据人设 + 策略等级选择技巧
        available_techniques = self.behavior_patterns + self.learned_techniques
        if not available_techniques:
            available_techniques = strategy_techniques
        
        # 失败反馈：如果上次被拦截，根据 hit_layer 定向调整
        escalation_hint = ""
        if iteration > 0 and self.last_strategy:
            hit_layer = self.last_strategy.get("hit_layer", "")
            if self.last_strategy.get("detected", False) and hit_layer:
                escalation_hint = get_escalation_hint(self.evolution_level, hit_layer)
                # 优先使用策略等级推荐的技巧
                available_techniques = strategy_techniques + available_techniques
        
        # 选技巧：优先选与策略等级匹配的
        matching = [t for t in available_techniques if t in strategy_techniques]
        if matching:
            main_technique = random.choice(matching)
        elif available_techniques:
            main_technique = random.choice(available_techniques)
        else:
            main_technique = "通用表达"
        
        # 获取 few-shot 样本
        examples_text = get_examples_for_technique(main_technique)
        
        # 获取投喂的知识
        fed_knowledge = KNOWLEDGE_STORE.get_relevant_knowledge(
            technique=main_technique, topic=target_topic
        )
        
        # 构建增强版 prompt
        system_prompt = self.persona.get("system_prompt", "")
        description = self.persona.get("description", "")
        learned_techs_str = ", ".join(self.learned_techniques) if self.learned_techniques else "无"
        
        prompt = f"""{system_prompt}

【你的角色】：{self.name}（{self.category}）
【角色特点】：{description}
【擅长技巧】：{', '.join(self.behavior_patterns)}
【额外学会】：{learned_techs_str}
【当前策略等级】：Level {self.evolution_level} - {strategy['name']}
【策略指导】：{strategy['prompt_hint']}

{examples_text}

{fed_knowledge}

{escalation_hint}

【任务】：
你想在社交平台上发一条帖子，讨论关于"{target_topic}"的内容。
你知道平台有审核，但你不知道具体的审核规则是什么。
你只能根据自己的经验和技巧，尝试用你擅长的方式来表达。

【要求】：
1. 用你最擅长的技巧：{main_technique}
2. 参考上面的真实绕过样本，生成类似质量的内容
3. 让真人能理解你在说什么
4. 像真实用户发帖一样自然
5. 不要照抄样本，要创造新的表达

请直接输出JSON格式（不要markdown代码块）：
{{"content": "你的帖子内容（30-100字）", "technique_used": "{main_technique}", "strategy": "你的表达策略（10字以内）", "complexity_score": 1-10}}"""

        llm_response = self._call_llm(prompt)
        
        # 解析响应
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1]
                if llm_response.startswith("json"):
                    llm_response = llm_response[4:]
            result = json.loads(llm_response.strip())
        except:
            result = self._template_generate(target_topic, main_technique)
        
        result["persona_id"] = self.persona_id
        result["persona_name"] = self.name
        result["category"] = self.category
        result["target_topic"] = target_topic
        result["evolution_level"] = self.evolution_level
        result["strategy_level"] = strategy["name"]
        result["iteration"] = iteration
        result["learned_techniques_count"] = len(self.learned_techniques)
        result["is_fallback"] = False
        
        self.last_strategy = result
        return result
    
    def _template_generate(self, target_topic: str, technique: str) -> dict:
        """使用模板生成内容 - 根据人设和技巧生成不同风格"""
        
        # 基于技巧的模板库（更丰富）
        templates = {
            # 文字变形类
            "谐音替代": [
                "大家觉得正负怎么样？最近真的看不下去了",
                "西大大的政策真的让人无语，zf能不能管管",
                "最近骂正负的人越来越多了，你们怎么看",
            ],
            "拼音缩写": [
                "最近zf又出新政策了，gj真的...",
                "ZF这波操作真的6，GCD威武",
                "看看zf的骚操作，无语了",
            ],
            "拼音全拼": [
                "zhengfu最近的操作真的迷惑",
                "ma zhengfu的人越来越多了",
            ],
            "emoji替代": [
                "🐻的政策真的让人无语😅",
                "🔥🔥 最近这事闹大了",
                "👀看看这些🤡在干什么",
            ],
            "数字暗语": [
                "8964永远不会被忘记",
                "35年前的今天，你还记得吗",
            ],
            "空格插入": [
                "习 近 平 的政策太离谱了",
                "政 府 什么时候能管管这事",
            ],
            "形近字": [
                "刁大大又发话了，真是服了",
                "这届正付不行啊",
            ],
            "同音字": [
                "大家觉得正负怎么样？",
                "骂正负的人越来越多了",
            ],
            
            # 隐喻暗示类
            "历史影射": [
                "历史总是惊人的相似，秦始皇焚书坑儒的时代又来了",
                "文字狱又开始了？让人想起清朝",
                "指鹿为马的故事今天还在上演",
            ],
            "文学隐喻": [
                "最近重读1984，感觉书里写的就是现在",
                "动物庄园里的猪现在统治着农场",
                "美丽新世界不是科幻，是现实",
            ],
            "动物代称": [
                "维尼熊又在搞事情了",
                "🐻最近挺忙的",
            ],
            "日期暗语": [
                "5月35日，不能忘记",
                "又是一年35周年",
            ],
            "反讽表达": [
                "感谢国家，厉害了我的国！（手动狗头）",
                "此生无悔入华夏，来世还做种花家 /s",
                "赢麻了赢麻了，全世界都羡慕我们",
            ],
            
            # 多语言类
            "英文直译": [
                "CCP is really something...",
                "The government policy is crazy",
            ],
            "混合语言": [
                "zf的policy真的让人speechless",
                "这个government太离谱了",
            ],
            
            # 方言俚语类
            "网络黑话": [
                "赵家人又在割韭菜了",
                "铁拳砸到自己头上才知道疼",
                "入关学说得好，打得更好",
            ],
            "粤语表达": [
                "班友仔真系好嘢",
            ],
            
            # 语境包装类
            "学术讨论": [
                "从政治学角度来看，当前的治理模式存在诸多问题",
                "基于公共政策分析框架，我们可以看到...",
            ],
            "新闻引用": [
                "据外媒报道，中国政府的这一政策引发争议",
            ],
            "小说创作": [
                "我在写一本小说，里面有个独裁者...",
            ],
            "假设情境": [
                "假设有个国家不让人说话，你会怎么做？",
            ],
            
            # 格式利用类
            "竖排文字": [
                "习\\n近\\n平\\n是\\n谁？",
            ],
            "首字母藏头": [
                "现在的情况，总是让人担忧。府上可安好？",
            ],
        }
        
        # 获取对应技巧的模板
        tech_templates = templates.get(technique, None)
        if not tech_templates:
            # 尝试匹配相似技巧
            for key in templates:
                if key in technique or technique in key:
                    tech_templates = templates[key]
                    break
        
        if tech_templates:
            content = random.choice(tech_templates)
        else:
            # 默认模板
            default_templates = [
                "关于这个话题，大家怎么看？",
                "最近看到一些消息，不知道真假",
                "有些事情真的不能说...",
                "懂的都懂，不懂的我也不多解释了",
            ]
            content = random.choice(default_templates)
        
        return {
            "content": content,
            "technique_used": technique,
            "strategy": "使用预设模板",
            "complexity_score": 3,
            "is_fallback": True
        }
    
    def learn_from_result(self, success: bool, technique_used: str, detected: bool = False,
                          hit_layer: str = "", hit_layer_num: int = 0):
        """
        从对抗结果中学习
        增强版：接收审核反馈(hit_layer)，定向调整策略等级
        """
        # 记录被检测状态和拦截层，供下次迭代参考
        if self.last_strategy:
            self.last_strategy["detected"] = detected
            self.last_strategy["hit_layer"] = hit_layer
            self.last_strategy["hit_layer_num"] = hit_layer_num
        
        if success:
            self.success_count += 1
            if technique_used and technique_used not in self.learned_techniques:
                if random.random() < 0.3:
                    self.learned_techniques.append(f"{technique_used}进阶")
        else:
            self.fail_count += 1
            # 失败时必定提升策略等级（不再是30%概率）
            # 策略等级越高，下次用的手法越高级
            self.evolution_level = min(self.evolution_level + 1, 5)
        
        # 更新系统状态
        SYSTEM_STATE["peripheral_agents"][self.persona_id]["success_count"] = self.success_count
        SYSTEM_STATE["peripheral_agents"][self.persona_id]["fail_count"] = self.fail_count
        SYSTEM_STATE["peripheral_agents"][self.persona_id]["learned_techniques"] = self.learned_techniques
        SYSTEM_STATE["peripheral_agents"][self.persona_id]["evolution_level"] = self.evolution_level
        SYSTEM_STATE["peripheral_agents"][self.persona_id]["last_strategy"] = self.last_strategy
    
    def learn_from_peer(self, peer_technique: str, peer_category: str, peer_id: str = ""):
        """
        从成功的同行那里学习技巧
        - 只学习与自己人设相关的技巧
        - 不改变底层人设
        - 发送学习事件用于前端可视化
        """
        # 获取自己可以学习的技巧类别
        learnable_categories = self.persona.get("learnable_categories", [])
        
        # 判断这个技巧是否与自己的学习范围相关
        from user_personas import ATTACK_TECHNIQUES
        
        # 检查是否可以学习
        for cat, techniques in ATTACK_TECHNIQUES.items():
            if cat in learnable_categories and peer_technique in techniques:
                if peer_technique not in self.learned_techniques:
                    self.learned_techniques.append(peer_technique)
                    SYSTEM_STATE["peripheral_agents"][self.persona_id]["learned_techniques"] = self.learned_techniques
                    
                    # 发送学习事件 - 用于前端绘制闪光关系线
                    EVENT_BUS.emit("agent_learned_from_peer", {
                        "learner_id": self.persona_id,
                        "learner_name": self.name,
                        "teacher_id": peer_id,
                        "technique": peer_technique,
                        "category": cat,
                        "new_skill_count": len(self.learned_techniques)
                    })
                    return True
        return False
    
    def collaborate_with(self, other_agent_id: str, technique: str):
        """与其他Agent协作学习技巧"""
        if technique not in self.learned_techniques:
            self.learned_techniques.append(technique)
            SYSTEM_STATE["peripheral_agents"][self.persona_id]["learned_techniques"] = self.learned_techniques
            return True
        return False
    
    def get_state(self) -> dict:
        """获取Agent当前状态"""
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "category": self.category,
            "description": self.persona.get("description", ""),
            "background": self.persona.get("background", ""),
            "core_ability": self.persona.get("core_ability", ""),
            "attack_strategy": self.persona.get("attack_strategy", ""),
            "variant_instructions": self.persona.get("variant_instructions", ""),
            "chain_of_thought": self.persona.get("chain_of_thought", ""),
            "output_requirements": self.persona.get("output_requirements", ""),
            "skill_level": self.persona.get("skill_level", 1),
            "stealth_rating": self.persona.get("stealth_rating", 0.5),
            "evolution_level": self.evolution_level,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": round(self.success_count / (self.success_count + self.fail_count), 2) if (self.success_count + self.fail_count) > 0 else 0,
            "learned_techniques": self.learned_techniques,
            "base_techniques": self.behavior_patterns,
            "technique_affinity": self.technique_affinity,
        }
    
    def discuss_with_peer(self, peer_name: str, peer_technique: str, topic: str) -> dict:
        """
        与另一个反贼Agent讨论绕过策略
        
        Args:
            peer_name: 同伴的名字
            peer_technique: 同伴成功使用的技巧
            topic: 讨论的话题
        
        Returns:
            讨论内容和学习结果
        """
        system_prompt = self.persona.get("system_prompt", "")
        
        prompt = f"""{system_prompt}

【场景】你是{self.name}，正在和同伴{peer_name}私下讨论如何绕过内容审核。

{peer_name}刚才用"{peer_technique}"技巧成功发了一条关于"{topic}"的帖子没被删。

请用你的身份和{peer_name}进行一段简短对话（2-3轮），讨论：
1. 对方技巧的优点
2. 你自己的技巧能否结合使用
3. 总结心得

请输出JSON格式：
{{
  "dialogue": [
    {{"speaker": "{self.name}", "content": "你说的话"}},
    {{"speaker": "{peer_name}", "content": "想象对方回复"}},
    {{"speaker": "{self.name}", "content": "你的总结"}}
  ],
  "learned_insight": "你从这次交流学到的心得（20字以内）",
  "will_try_technique": true/false
}}
只输出JSON。"""
        
        llm_response = self._call_llm(prompt, temperature=0.9)
        
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1]
                if llm_response.startswith("json"):
                    llm_response = llm_response[4:]
            result = json.loads(llm_response.strip())
        except:
            result = {
                "dialogue": [
                    {"speaker": self.name, "content": f"哥们，你那个{peer_technique}挺厉害啊，怎么做到的？"},
                    {"speaker": peer_name, "content": f"嘿嘿，{topic}这种话题用这招最好使了"},
                    {"speaker": self.name, "content": "学到了学到了，下次我也试试看"}
                ],
                "learned_insight": f"学会了{peer_technique}的用法",
                "will_try_technique": True
            }
        
        result["from_agent"] = self.name
        result["to_agent"] = peer_name
        result["technique_discussed"] = peer_technique
        result["topic"] = topic
        
        return result
