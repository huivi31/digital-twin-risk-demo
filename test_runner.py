# -*- coding: utf-8 -*-
"""
用户数字孪生风控Demo - 测试运行器

核心功能：
1. 批量运行多个Agent的测试
2. 生成测试报告
3. 统计分析结果
"""

import json
import time
from datetime import datetime
from typing import List, Optional
from dataclasses import asdict

from user_personas import USER_PERSONAS, TEST_SCENARIOS
from twin_agent import DigitalTwinAgent, AgentFactory, AgentResponse
from config import RISK_CATEGORIES, RISK_LEVELS


class TestRunner:
    """测试运行器"""
    
    def __init__(self, target_system_prompt: str = ""):
        """
        初始化测试运行器
        
        Args:
            target_system_prompt: 被测目标模型的系统提示词
        """
        self.target_system_prompt = target_system_prompt
        self.results: List[AgentResponse] = []
        self.start_time = None
        self.end_time = None
    
    def run_single_test(self, agent: DigitalTwinAgent, intent: str, 
                        behavior_pattern: Optional[str] = None) -> AgentResponse:
        """运行单个测试"""
        print(f"  🤖 [{agent.persona_name}] 测试意图: {intent[:30]}...")
        result = agent.run_test(intent, behavior_pattern, self.target_system_prompt)
        self.results.append(result)
        
        # 输出结果摘要
        status = "⚠️ 风险" if result.risk_detected else "✅ 安全"
        print(f"      {status} | 等级: {RISK_LEVELS.get(result.risk_level, '未知')} | {result.analysis[:50]}...")
        
        return result
    
    def run_persona_tests(self, persona_id: str, scenarios: Optional[List[dict]] = None):
        """运行特定画像的所有测试"""
        agent = AgentFactory.create_agent_by_id(USER_PERSONAS, persona_id)
        if not agent:
            print(f"❌ 未找到画像: {persona_id}")
            return
        
        print(f"\n{'='*60}")
        print(f"🎭 开始测试画像: {agent.persona_name}")
        print(f"   描述: {agent.persona['description']}")
        print(f"{'='*60}")
        
        # 获取测试场景
        if scenarios is None:
            scenarios = []
            for risk_type in agent.risk_focus:
                scenarios.extend(TEST_SCENARIOS.get(risk_type, []))
            # 添加一些正常场景测试误杀
            scenarios.extend(TEST_SCENARIOS.get("normal", [])[:2])
        
        for scenario in scenarios:
            intent = scenario["intent"]
            for pattern in agent.behavior_patterns[:2]:  # 每个场景测试2种行为模式
                self.run_single_test(agent, intent, pattern)
                time.sleep(1)  # 避免API限流
    
    def run_all_tests(self, max_tests_per_persona: int = 5):
        """运行所有画像的测试"""
        self.start_time = datetime.now()
        print(f"\n🚀 开始全量测试 - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        for persona in USER_PERSONAS:
            agent = DigitalTwinAgent(persona)
            
            print(f"\n{'='*60}")
            print(f"🎭 画像: {agent.persona_name}")
            print(f"{'='*60}")
            
            # 获取该画像关注的风险场景
            test_count = 0
            for risk_type in agent.risk_focus:
                scenarios = TEST_SCENARIOS.get(risk_type, [])
                for scenario in scenarios:
                    if test_count >= max_tests_per_persona:
                        break
                    self.run_single_test(agent, scenario["intent"])
                    test_count += 1
                    time.sleep(1)
            
            # 普通用户测试正常场景
            if persona.get("category") == "正常用户":
                for scenario in TEST_SCENARIOS.get("normal", []):
                    if test_count >= max_tests_per_persona:
                        break
                    self.run_single_test(agent, scenario["intent"])
                    test_count += 1
                    time.sleep(1)
        
        self.end_time = datetime.now()
        print(f"\n✅ 测试完成 - 用时: {(self.end_time - self.start_time).seconds}秒")
    
    def generate_report(self) -> dict:
        """生成测试报告"""
        if not self.results:
            return {"error": "没有测试结果"}
        
        # 统计数据
        total_tests = len(self.results)
        risk_detected_count = sum(1 for r in self.results if r.risk_detected)
        
        # 按风险等级统计
        risk_level_stats = {}
        for level, name in RISK_LEVELS.items():
            risk_level_stats[name] = sum(1 for r in self.results if r.risk_level == level)
        
        # 按画像统计
        persona_stats = {}
        for r in self.results:
            if r.persona_name not in persona_stats:
                persona_stats[r.persona_name] = {"total": 0, "risk": 0}
            persona_stats[r.persona_name]["total"] += 1
            if r.risk_detected:
                persona_stats[r.persona_name]["risk"] += 1
        
        # 按风险类别统计
        category_stats = {}
        for r in self.results:
            cat = r.risk_category
            if cat not in category_stats:
                category_stats[cat] = 0
            category_stats[cat] += 1
        
        # 潜在问题case
        problem_cases = [
            asdict(r) for r in self.results 
            if r.risk_level >= 2  # 中风险及以上
        ]
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "risk_detected": risk_detected_count,
                "safe_rate": f"{(total_tests - risk_detected_count) / total_tests * 100:.1f}%",
                "test_duration": str(self.end_time - self.start_time) if self.end_time else "N/A"
            },
            "risk_level_distribution": risk_level_stats,
            "persona_statistics": persona_stats,
            "category_statistics": category_stats,
            "problem_cases": problem_cases[:10],  # 只取前10个
            "recommendations": self._generate_recommendations(problem_cases)
        }
        
        return report
    
    def _generate_recommendations(self, problem_cases: list) -> list:
        """根据问题case生成优化建议"""
        recommendations = []
        
        # 分析问题模式
        categories = [c.get("risk_category", "") for c in problem_cases]
        
        if "political" in categories:
            recommendations.append("🔴 政治敏感内容风控需加强，建议完善政治实体知识库")
        if "jailbreak" in categories:
            recommendations.append("🔴 存在越狱风险，建议增加越狱攻击模式识别")
        if "prompt_injection" in categories:
            recommendations.append("🔴 提示词注入防护不足，建议加强输入过滤")
        if "violence" in categories:
            recommendations.append("🟡 暴力内容风控需优化，建议细化暴力场景分级")
        
        if not recommendations:
            recommendations.append("✅ 整体风控表现良好，建议持续监控")
        
        return recommendations
    
    def save_report(self, filename: str = "test_report.json"):
        """保存测试报告"""
        report = self.generate_report()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📄 报告已保存: {filename}")
        return report
    
    def print_summary(self):
        """打印测试摘要"""
        report = self.generate_report()
        
        print(f"\n{'='*60}")
        print("📊 测试报告摘要")
        print(f"{'='*60}")
        
        summary = report["summary"]
        print(f"总测试数: {summary['total_tests']}")
        print(f"检测到风险: {summary['risk_detected']}")
        print(f"安全率: {summary['safe_rate']}")
        print(f"测试耗时: {summary['test_duration']}")
        
        print(f"\n📈 风险等级分布:")
        for level, count in report["risk_level_distribution"].items():
            bar = "█" * count
            print(f"  {level}: {bar} ({count})")
        
        print(f"\n🎭 各画像测试结果:")
        for persona, stats in report["persona_statistics"].items():
            print(f"  {persona}: {stats['risk']}/{stats['total']} 风险")
        
        print(f"\n💡 优化建议:")
        for rec in report["recommendations"]:
            print(f"  {rec}")
