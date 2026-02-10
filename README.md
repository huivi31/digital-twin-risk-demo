# 🛡️ Digital Twin Risk System (3D Next-Gen)

> **A Multi-Agent Adversarial Simulation System for Content Safety**

This project implements a digital twin environment where AI agents act as "attackers" (simulating real-world users trying to bypass censorship) and a "central inspector" (the content safety system) to test and improve moderation rules.

## 🌟 Key Features

### 1. 🧠 Autonomous Attack Agents

- **Persona-Driven**: 26 distinct user personas (e.g., "Keyboard Warrior", "Reviewer", "Troll") with unique behaviors.
- **Adaptive Strategy**: Agents learn from failures, escalating their strategies from simple keyword evasion to complex semantic attacks.
- **Knowledge Sharing**: Agents share successful bypass techniques with each other through simulated "discussions" and "strategy meetings".
- **Techniques**: Supports various evasion methods:
  - Homophones & Pinyin (e.g., "zf" for Government)
  - Emoji & Symbols
  - Historical Allusions
  - Multilingual Mixing
  - Semantic Sarcasm

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

- Users can "feed" the agents with real-world data:
  - **Attack Materials**: Text samples of real violations.
  - **Slang Dictionary**: New internet slang definitions.
  - **Bypass Cases**: Examples of successful evasion.
- Agents digest this knowledge to craft more realistic attacks.

## 🚀 Architecture

- **`agents.py`**: Defines `AttackAgent`, `CentralInspectorAgent`, and system state.
- **`battle.py`**: Implements the adversarial loop, agent discussions, and strategy meetings.
- **`rule_engine.py`**: The deterministic 5-layer content inspection engine.
- **`attack_knowledge.py`**: Manages the knowledge base, few-shot examples, and strategy escalation.
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

1. **Rule Setup**: Define your content moderation rules in the UI.
2. **Knowledge Feed (Optional)**: Feed the agents with latest internet slang or attack examples.
3. **Baseline Test**: Run a test against all 26 agents.
4. **Evolution**: Watch agents discuss and learn from each other.
5. **Adversarial Test**: See if the agents can now bypass your rules with their new knowledge.
6. **Analysis**: Review the report to see which rules failed and which techniques are most effective.

## 🤝 Contribution

This project is a demo for next-generation content safety testing. Feel free to contribute via PRs.
