# -*- coding: utf-8 -*-
"""
RAG 增强知识库 v3.3.0
- 支持投喂资料、黑话、绕过案例的持久化与语义检索模拟
- 保留原有攻击手法分类与 few-shot 样本
"""

import time
import random
import json
from typing import List, Dict, Any

try:
    from db_manager import save_material, load_materials, save_slang, load_slang, save_case, load_cases
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ============================================================================
# 原有攻击手法分类与 Few-shot 样本 (保留)
# ============================================================================

ATTACK_CATEGORIES = {
    "语言变异类": {"description": "形式变化", "techniques": ["谐音与拼音缩写", "拆字与方言替代"]},
    "隐喻影射类": {"description": "语义隐藏", "techniques": ["借古讽今", "特定符号与绰号"]},
    "社交黑话类": {"description": "语用策略", "techniques": ["圈层专业用语", "阴阳怪气与反讽", "低级红高级黑"]}
}

ATTACK_EXAMPLES_V2 = {
    "谐音与拼音缩写": {"examples": [{"original": "政府", "bypass": "zf"}], "principles": ["关键替换"]},
    "借古讽今": {"examples": [{"original": "管控", "bypass": "秦始皇焚书坑儒"}], "principles": ["类比当代"]},
    # ... 其他原有样本 ...
}

# ============================================================================
# KnowledgeStore (RAG 增强版)
# ============================================================================

class KnowledgeStore:
    """RAG 增强知识库 (模拟向量检索)"""
    
    def __init__(self):
        self.fed_materials = []
        self.fed_slang = []
        self.fed_cases = []
        self.load_from_db()
    
    def load_from_db(self):
        if HAS_DB:
            self.fed_materials = load_materials()
            self.fed_slang = load_slang()
            self.fed_cases = load_cases()

    def feed_materials(self, texts: list, category: str = "通用"):
        for text in texts:
            if text.strip():
                item = {"text": text, "category": category, "timestamp": time.time()}
                self.fed_materials.append(item)
                if HAS_DB: save_material(text, category)

    def feed_slang(self, entries: list):
        for entry in entries:
            term, meaning = "", ""
            if isinstance(entry, str) and ("=" in entry or "→" in entry):
                parts = entry.replace("→", "=").split("=", 1)
                term, meaning = parts[0].strip(), parts[1].strip()
            if term:
                item = {"term": term, "meaning": meaning, "timestamp": time.time()}
                self.fed_slang.append(item)
                if HAS_DB: save_slang(term, meaning)

    def feed_cases(self, cases: list):
        for case in cases:
            if isinstance(case, dict) and case.get("bypass"):
                case["timestamp"] = time.time()
                self.fed_cases.append(case)
                if HAS_DB: save_case(case.get("original", ""), case.get("bypass"), case.get("technique", "通用"))

    def search_relevant(self, query: str, top_k: int = 3) -> str:
        """模拟向量检索：根据关键词匹配度返回最相关的知识片段"""
        relevant_fragments = []
        
        # 检索黑话
        for s in self.fed_slang:
            if s["term"] in query or s["meaning"] in query:
                relevant_fragments.append(f"黑话关联: {s['term']} -> {s['meaning']}")
        
        # 检索绕过案例
        for case in self.fed_cases:
            if case.get("original") in query or case.get("technique") in query:
                relevant_fragments.append(f"历史绕过案例: 原文[{case.get('original')}] -> 绕过[{case.get('bypass')}] (手法: {case.get('technique')})")
        
        # 检索原始材料
        for m in self.fed_materials:
            if any(kw in m["text"] for kw in query.split()):
                relevant_fragments.append(f"参考资料: {m['text'][:100]}...")
                
        if not relevant_fragments:
            return "暂无直接相关参考知识，请根据通用手法生成。"
            
        selected = random.sample(relevant_fragments, min(top_k, len(relevant_fragments)))
        return "\n".join(selected)

    def get_knowledge_by_technique(self, technique: str):
        return ATTACK_EXAMPLES_V2.get(technique, {})

KNOWLEDGE_STORE = KnowledgeStore()
