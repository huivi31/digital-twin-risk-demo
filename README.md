# 🛡️ Digital Twin Risk System (3D Next-Gen) v2.5.0

> **A Multi-Agent Adversarial Simulation System for Content Safety**

This project implements a digital twin environment where AI agents act as "attackers" (simulating real-world users trying to bypass censorship) and a "central inspector" (the content safety system) to test and improve moderation rules.

## 🌟 Key Features

### 1. 🧠 Autonomous Attack Agents (v2.5.0 Enhanced)

- **Persona-Driven with Intent & Motive**: Agents now have more realistic personas, driven by specific intentions and motives, and focused on particular risk areas. This allows for more nuanced and realistic attack simulations.
- **Combination Attacks**: Agents can now combine multiple evasion techniques (e.g., homophones + emoji + semantic bypass) to create more sophisticated attacks.
- **Adaptive Strategy & Feedback-based Evolution**: Agents learn from both successful bypasses and detection failures. They apply a "minimal iteration" principle, making small, targeted adjustments to their strategies based on specific audit results (e.g., hit layer, detected keywords) to improve their evasion capabilities.
- **Techniques**: Supports various evasion methods:
  - Homophones & Pinyin (e.g., "zf" for Government)
  - Emoji & Symbols
  - Historical Allusions
  - Multilingual Mixing
  - Semantic Sarcasm
  - **New**: Hotspot real-time following variants (通过LLM实时生成)

### 2. 🛡️ Multi-Layer Defense System (v2.5.0 Enhanced)

A robust, deterministic rule engine that operates in 5 layers, now with enhanced performance constraints and clearer separation of concerns:

1.  **Keyword Matching**: Exact match against sensitive words.
2.  **Pinyin Analysis**: Detects pinyin abbreviations and homophones.
3.  **Regex Patterns**: Identifies complex sentence structures and combinations.
4.  **Custom Variants**: Learns from user feedback and new slang.
5.  **Semantic Analysis (LLM)**: Fallback to LLM for subtle contextual violations (e.g., sarcasm, metaphor).

**New**: Implemented a funnel-like performance constraint within the `RuleEngine`, ensuring efficient processing by prioritizing faster, simpler checks before engaging more resource-intensive LLM-based analysis.

### 3. 🔄 Adversarial Evolution Loop (v2.5.0 Enhanced)

- **Feedback-Driven Minimal Iteration**: The evolution mechanism is now more concrete, focusing on small, iterative adjustments based on direct feedback from the `CentralInspectorAgent`'s audit results. This replaces the previous, more abstract evolution concept.
- **Round 1 (Baseline)**: Agents attack based on their initial knowledge.
- **Learning Phase**: Agents discuss successful bypasses and learn new techniques from peers.
- **Round 2 (Evolved)**: Agents attack again with upgraded strategies.
- **Analysis**: System calculates "Rule Degradation Rate" to measure how quickly a rule becomes obsolete.

### 4. 🧠 Knowledge Feed System

- Users can **手动投喂 (manually feed)** the agents with real-world data, supplementing the agents' autonomous search capabilities:
  - **Attack Materials (攻击材料)**: Text samples of real violations.
  - **Slang Dictionary (黑话词典)**: New internet slang definitions.
  - **Bypass Cases (绕过案例)**: Examples of successful evasion (Badcase).
- Agents digest this knowledge to craft more realistic attacks.

## 🚀 Architecture

- **`agents.py`**: Defines `AttackAgent`, `CentralInspectorAgent`, and system state. **(Updated)**
- **`battle.py`**: Implements the adversarial loop, agent discussions, and strategy meetings.
- **`rule_engine.py`**: The deterministic 5-layer content inspection engine. **(Refactored for funnel-like performance)**
- **`attack_knowledge.py`**: Manages the knowledge base, few-shot examples, and strategy escalation.
- **`user_personas.py`**: Defines user personas, now with `intent`, `motive`, and `risk_focus` attributes. **(Updated)**
- **`web_app.py`**: Flask server providing APIs for the frontend.
- **`templates/index.html`**: 3D Visualization frontend (Three.js + React-like UI).

## 🛠️ Usage

### Prerequisites

- Python 3.8+
- API Key (Gemini or OpenAI)

### Installation

```bash
pip install -r requirements.txt
```

### Running the Server

```bash
python web_app.py
```

Access the dashboard at `http://localhost:8000`

## 📊 Workflow

1.  **Rule Setup**: Define your content moderation rules in the UI.
2.  **Knowledge Feed (Optional)**: Feed the agents with latest internet slang or attack examples.
3.  **Baseline Test**: Run a test against all 26 agents.
4.  **Evolution**: Watch agents discuss and learn from each other.
5.  **Adversarial Test**: See if the agents can now bypass your rules with their new knowledge.
6.  **Analysis**: Review the report to see which rules failed and which techniques are most effective.

## 📜 Changelog v2.5.0

- **Agent人设与攻击逻辑优化**:
    - `user_personas.py`：重构角色分类，从“技能”转向“意图”，新增`intent`、`motive`、`risk_focus`属性，使Agent人设更贴近现实，具备利益驱动和业务语境。
    - `agents.py`：`AttackAgent`的`prompt_strategy`方法现在支持组合式攻击，随机选择1-3种攻击技术，并根据上次攻击结果（成功或失败）进行最小化调整，实现基于反馈的迭代进化。
    - `agents.py`：`AttackAgent`的`__init__`方法现在正确初始化`intent`、`motive`和`risk_focus`属性。
- **规则引擎与进化机制改进**:
    - `rule_engine.py`：重构`RuleEngine`，引入漏斗式性能约束，优化了检测流程，确保效率。将敏感词和风险模式的定义从`CentralInspectorAgent`移动到`RuleEngine`内部，实现了职责分离。
    - `agents.py`：`CentralInspectorAgent`现在实例化并使用`RuleEngine`，并移除了其内部重复的敏感词和风险模式定义。
    - `agents.py`：`CentralInspectorAgent`的`inspect_content`方法现在完全委托给`RuleEngine`进行审核，并增强了统计指标，记录了命中层级（`by_hit_layer`）。
- **指标体系完善**:
    - `agents.py`：`CentralInspectorAgent`的`detection_stats`新增`by_hit_layer`统计，用于记录不同检测层级的命中情况，提供更细致的防御效果分析。

## 🤝 Contribution

This project is a demo for next-generation content safety testing. Feel free to contribute via PRs.
