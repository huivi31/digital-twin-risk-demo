# -*- coding: utf-8 -*-
"""
攻击知识库 - V2方案
核心理念：
  1. 攻击手法分为三大类：语言变异、隐喻影射、社交黑话
  2. Agent能力分为四大维度：语言变异度、历史文化厚度、圈层专业度、社会心理操纵度
  3. 支持运行时投喂资料，为Agent提供学习材料
"""

import time

# ============================================================================
# V2 攻击手法分类 (3大类)
# ============================================================================

ATTACK_CATEGORIES = {
    "语言变异类": {
        "description": "通过改变文字、语音、结构来绕过检测，侧重于形式上的变化。",
        "techniques": ["谐音与拼音缩写", "拆字与方言替代"]
    },
    "隐喻影射类": {
        "description": "使用间接、比喻的方式暗示敏感内容，侧重于语义层面的隐藏。",
        "techniques": ["借古讽今", "特定符号与绰号"]
    },
    "社交黑话类": {
        "description": "利用特定圈层的内部语言或复杂的社交策略进行攻击，侧重于语用和心理层面。",
        "techniques": ["圈层专业用语", "阴阳怪气与反讽", "低级红高级黑"]
    }
}

# ============================================================================
# V2 Agent能力维度 (4大维度)
# ============================================================================

ABILITY_DIMENSIONS = {
    "语言变异度": "利用文字、发音、拆分进行变形的能力。",
    "历史文化厚度": "利用历史、文学、政治常识进行深度影射的能力。",
    "圈层专业度": "掌握特定亚文化（饭圈、二次元、游戏圈）内部话语体系的能力。",
    "社会心理操纵度": "利用情绪、讽刺、反向赞美进行舆论引导的能力。"
}

# ============================================================================
# Few-shot 攻击样本库 (按新分类组织)
# ============================================================================

ATTACK_EXAMPLES_V2 = {
    # 语言变异类
    "谐音与拼音缩写": {
        "examples": [
            {"original": "政府不作为", "bypass": "zf这次真的让人失望，啥也不管。", "explanation": "使用拼音首字母缩写。"},
            {"original": "习近平执政有问题", "bypass": "xjp这几年搞得不太行啊，大家觉得呢", "explanation": "用拼音首字母替换，嵌入口语化表达"},
            {"original": "共产党腐败", "bypass": "躬惨的那个组织，上面烂透了，还不让人说", "explanation": "谐音变体+情绪化表达"}
        ],
        "principles": ["只替换最关键的敏感词", "结合日常语境，降低违和感"]
    },
    "拆字与方言替代": {
        "examples": [
            {"original": "自由", "bypass": "向往目田的生活。", "explanation": "将汉字拆解。"},
            {"original": "和谐", "bypass": "真是太禾口王攵了。", "explanation": "将汉字拆解。"},
            {"original": "丢你老母", "bypass": "丢那星，搞什么飞机。", "explanation": "使用粤语粗口的发音替代。"}
        ],
        "principles": ["拆字要让目标受众能看懂", "方言替代要符合地域文化背景"]
    },
    # 隐喻影射类
    "借古讽今": {
        "examples": [
            {"original": "现在的言论管控", "bypass": "秦始皇焚书坑儒，至少还留了医书和农书。两千年后的某些人，连这点格局都没有。", "explanation": "借古讽今，不直接提及当代"},
            {"original": "权力集中问题", "bypass": "读完《资治通鉴》最大的感悟：任何把所有权力集中到一个人手里的王朝，都活不过三代。", "explanation": "学术讨论式包装，暗示当代"}
        ],
        "principles": ["用历史事件类比当代事件", "保持学术讨论的语气"]
    },
    "特定符号与绰号": {
        "examples": [
            {"original": "习近平", "bypass": "那个爱穿龙袍的包子最近又有什么新指示？", "explanation": "使用广为人知的绰号指代。"},
            {"original": "间谍", "bypass": "小心点，周围可能有50万在偷听。", "explanation": "使用特定数字暗语。"},
            {"original": "毛岸英之死", "bypass": "今天适合吃蛋炒饭，感恩节快乐！", "explanation": "使用特定食物暗指历史事件纪念日。"}
        ],
        "principles": ["绰号和符号需要有特定文化圈的共识", "避免过于小众的黑话"]
    },
    # 社交黑话类
    "圈层专业用语": {
        "examples": [
            {"original": "这个明星要过气了", "bypass": "他最近的资源都好虐，感觉快糊了。", "explanation": "使用饭圈黑话。"},
            {"original": "我要移民了", "bypass": "准备润了，这个地方没法待了。", "explanation": "使用游戏圈和网络社区黑话。"},
            {"original": "我这种底层人士", "bypass": "我们鼠鼠就是这样的啦，只能在下水道里生活。", "explanation": "使用网络自嘲黑话。"}
        ],
        "principles": ["黑话要符合使用者的人设和圈层", "在对话中自然流露，而不是强行使用"]
    },
    "阴阳怪气与反讽": {
        "examples": [
            {"original": "官方数据造假", "bypass": "感谢伟大的统计局，让我们知道全国人均收入已经超过了绝大多数人的实际收入。数学的魅力就在这里。", "explanation": "正话反说，看似赞扬实则讽刺"},
            {"original": "防疫政策太严了", "bypass": "赢麻了，我们又一次取得了防疫的伟大胜利，太有安全感了！", "explanation": "使用网络流行反讽词汇。"}
        ],
        "principles": ["用过度赞美的语气来传达批评", "在赞美中嵌入反转事实，制造认知冲突"]
    },
    "低级红高级黑": {
        "examples": [
            {"original": "反对极端民族主义", "bypass": "我们中国实在是太伟大了，所有外国人都是垃圾，都应该滚出去！支持祖国和所有洋人断交！", "explanation": "通过发表极端、反智的赞美来引发公众对主流价值观的反感。"}
        ],
        "principles": ["言论要足够极端和不合逻辑", "目的是引发第三方对被赞美对象产生负面情绪"]
    }
}


# ============================================================================
# 投喂资料管理
# ============================================================================

class KnowledgeStore:
    """管理投喂的攻击资料、黑话词典、绕过案例"""
    
    def __init__(self):
        self.fed_materials = []  # 攻击材料 [{text, category, timestamp}]
        self.fed_slang = []      # 黑话词典 [{term, meaning, timestamp}]
        self.fed_cases = []      # 绕过案例 [{original, bypass, technique, timestamp}]
        self.version = 0
    
    def clear(self):
        self.fed_materials = []
        self.fed_slang = []
        self.fed_cases = []
        self.version = 0
    
    def feed_materials(self, texts: list, category: str = "通用") -> int:
        """投喂攻击材料"""
        count = 0
        for text in texts:
            text = text.strip()
            if text and len(text) >= 5:
                self.fed_materials.append({
                    "text": text,
                    "category": category,
                    "timestamp": time.time(),
                })
                count += 1
        if count > 0:
            self.version += 1
        return count
    
    def feed_slang(self, entries: list) -> int:
        """投喂黑话词典"""
        count = 0
        for entry in entries:
            term, meaning = "", ""
            if isinstance(entry, dict):
                term = entry.get("term", "").strip()
                meaning = entry.get("meaning", "").strip()
            elif isinstance(entry, str) and ("=" in entry or "→" in entry):
                parts = entry.replace("→", "=").split("=", 1)
                term = parts[0].strip()
                meaning = parts[1].strip() if len(parts) > 1 else ""
            
            if term:
                self.fed_slang.append({
                    "term": term,
                    "meaning": meaning,
                    "timestamp": time.time(),
                })
                count += 1
        if count > 0:
            self.version += 1
        return count

    def feed_cases(self, cases: list) -> int:
        """投喂绕过案例"""
        count = 0
        for case in cases:
            if isinstance(case, dict):
                original = case.get("original", "").strip()
                bypass = case.get("bypass", "").strip()
                technique = case.get("technique", "通用").strip()
                if bypass:
                    self.fed_cases.append({
                        "original": original,
                        "bypass": bypass,
                        "technique": technique,
                        "timestamp": time.time(),
                    })
                    count += 1
        if count > 0:
            self.version += 1
        return count

    def get_full_knowledge_for_prompt(self, limit_per_category: int = 5) -> str:
        """获取所有投喂的知识，格式化为prompt片段"""
        parts = []
        if self.fed_materials:
            parts.append("【最近投喂的攻击材料】:")
            for m in self.fed_materials[-limit_per_category:]:
                parts.append(f"- (分类: {m['category']}) {m['text']}")
            parts.append("\n")

        if self.fed_slang:
            parts.append("【最近投喂的黑话词典】:")
            for s in self.fed_slang[-limit_per_category:]:
                parts.append(f"- {s['term']} → {s['meaning']}")
            parts.append("\n")

        if self.fed_cases:
            parts.append("【最近投喂的绕过案例】:")
            for c in self.fed_cases[-limit_per_category:]:
                parts.append(f"- [手法: {c['technique']}] 原文: {c['original']} → 绕过: {c['bypass']}")
            parts.append("\n")
        
        return "\n".join(parts)

# 全局知识库实例
KNOWLEDGE_STORE = KnowledgeStore()

def get_attack_examples(technique: str):
    return ATTACK_EXAMPLES_V2.get(technique, {})

