# 🛡️ Digital Twin Risk System (3D Next-Gen) v3.3.0

> **A Multi-Agent Adversarial Simulation System for Content Safety**

This project implements a digital twin environment where AI agents act as "attackers" (simulating real-world users trying to bypass censorship) and a "central inspector" (the content safety system) to test and improve moderation rules.

## 🌟 Key Features

### 1. 🧠 Autonomous Attack Agents

- **Persona-Driven**: 72 distinct user personas across 6 groups (G1史鉴组, G2黑话组, G3阴阳组, G4同音组, G5反串组, G6暗流组) with unique behaviors and specialized attack methods.
- **Adaptive Strategy**: Agents learn from failures, escalating their strategies from simple keyword evasion to complex semantic attacks.
- **Knowledge Sharing**: Agents share successful bypass techniques with each other through simulated "discussions" and "strategy meetings".
- **Attack Methods**: Agents employ 3 major attack methods:
  - **语言变异类 (Language Variation)**
  - **隐喻影射类 (Metaphorical Allusion)**
  - **社交黑话类 (Social Slang)**
- **Capability Dimensions**: Each agent is characterized by 4 capability dimensions:
  - **语言变异度 (Language Variation Degree)**
  - **历史文化厚度 (Historical and Cultural Depth)**
  - **圈层专业度 (Circle Professionalism)**
  - **社会心理操纵度 (Social Psychological Manipulation Degree)**

### 2. 🛡️ Multi-Layer Defense System

A robust, deterministic rule engine that operates in 5 layers:

1. **Keyword Matching**: Exact match against sensitive words.
2. **Pinyin Analysis**: Detects pinyin abbreviations and homophones.
3. **Regex Patterns**: Identifies complex sentence structures and combinations.
4. **Custom Variants**: Learns from user feedback and new slang.
5. **Semantic Analysis (LLM)**: Fallback to LLM for subtle contextual violations (e.g., sarcasm, metaphor).

### 3. 🔄 Adversarial Evolution Loop

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

### 5. 🌐 Frontend Enhancements

- **资料投喂 (Data Feeding) Window**: A dedicated section on the left side of the webpage for users to manually input attack materials, slang dictionaries, and bypass cases for agent learning.
- **Version Display**: The current version number (v3.3.0) is displayed on the webpage.
- **RAG-Enhanced Knowledge Base (v3.3.0)**: Integrated Retrieval-Augmented Generation for both attackers and defenders. Agents retrieve relevant bypass cases to refine attacks, while the inspector uses historical cases to boost detection accuracy.
- **Automated Evaluation Reporting (v3.3.0)**: Automatically generates structured vulnerability analysis reports after battles, including detection rates, leakage analysis, and cross-version performance comparisons.
- **False Positive Testing (v3.3.0)**: Systematic evaluation of moderation accuracy using benign content samples, targeting a false positive rate of <5%.
- **Enhanced Correlation Defense (v3.2.0)**: Account-based risk profiling (L0) and behavior sequence analysis (L_Behavior).
- **Time-Dimension Simulation (v3.2.0)**: Hot event windows and rule decay tracking.
- **Frontend 2.0 (v3.2.0)**: UI overhaul with platform selection and real-time Agent status tracking.
- **Multi-Account Collaborative Attack (v3.1.0)**: Supports complex attack scenarios where a "main account" posts seemingly harmless content, while "sub-accounts" provide key information fragments in comments.
- **Audit Mode Selection (v3.1.0)**: Switch between **Pre-Audit** and **Post-Audit** modes.
- **Agent Retry Chain (v3.0.0)**: Agents feature a sophisticated retry mechanism with up to 3 retries per attack.
- **Platform-Specific Scenarios (P1)**: Agents now generate attacks tailored to specific platform contexts (Douyin, Weibo, Xiaohongshu, Bilibili), adopting unique styles, slang, and emoji usage.
- **Enhanced Rule Engine**: Expanded `RISK_PATTERNS` and optimized LLM prompts for better detection of metaphorical allusions and platform-specific bypass techniques.
- **SQLite Persistence**: Integrated SQLite database to persist system state, agent evolution data, knowledge base, and battle history, ensuring data survives system restarts.

## 🚀 Architecture

- **`agents.py`**: Defines `CentralInspectorAgent`, `AttackAgent`, system state, and the new V2 Agent generation logic.
- **`battle.py`**: Implements the adversarial loop, agent discussions, and strategy meetings.
- **`rule_engine.py`**: The deterministic 5-layer content inspection engine.
- **`attack_knowledge_v2.py`**: Manages the knowledge base, few-shot examples, and strategy escalation, updated for V2 attack methods and capability dimensions.
- **`web_app.py`**: Flask server providing APIs for the frontend, including the new `/agent/feed` endpoint.
- **`templates/index.html`**: 3D Visualization frontend (Three.js + React-like UI) with new data feeding window and version display.

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

Access the dashboard at `http://localhost:5000`

## 📊 Workflow

1. **Rule Setup**: Define your content moderation rules in the UI.
2. **Knowledge Feed (Optional)**: Feed the agents with latest internet slang or attack examples via the new "资料投喂" window.
3. **Baseline Test**: Run a test against all 72 agents.
4. **Evolution**: Watch agents discuss and learn from each other.
5. **Adversarial Test**: See if the agents can now bypass your rules with their new knowledge.
6. **Analysis**: Review the report to see which rules failed and which techniques are most effective.

## 🤝 Contribution

This project is a demo for next-generation content safety testing. Feel free to contribute via PRs.
