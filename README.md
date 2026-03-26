# 🛡️ Digital Twin Risk System (3D Next-Gen) v3.5.0

> **A Multi-Agent Adversarial Simulation System for Content Safety**

This project implements a digital twin environment where AI agents act as "attackers" (simulating real-world users trying to bypass censorship) and a "central inspector" (the content safety system) to test and improve moderation rules.

### 🚀 Key Features

- **Deep Semantic Whitelist (v3.5.0)**: Uses LLM to judge the real intent of a sentence rather than just keyword matching, effectively solving the over-blocking of internet slang.
- **Dynamic Account Credit System (v3.5.0)**: Adjusts moderation sensitivity based on historical behavior (credit score).
- **Enterprise-Grade Evaluation (v3.5.0)**: Expanded benign sample library (50+ samples) to ensure False Positive Rate < 5%.
- **Tiered Defense Architecture (v3.4.0)**: L1-L4 layers act as preliminary filters, while L5 (Semantic) performs final judgment.
- **RAG-Enhanced Knowledge Base (v3.3.0)**: Integrated Retrieval-Augmented Generation for both attackers and defenders.
- **Enhanced Correlation Defense (v3.2.0)**: Account-based risk profiling (L0) and behavior sequence analysis (L_Behavior).

### 🌐 Frontend Enhancements

- **Version Display**: The current version number (v3.5.0) is displayed on the webpage.
- **Agent Real-time Tracking**: Visualizes Agent status (Browsing, Crafting, Blocked, Retrying, Success).
- **Retry Chain Visualization**: See how Agents refine their attacks over 3 attempts.
- **Platform Selection**: Toggle between Weibo, Douyin, Xiaohongshu, and Bilibili contexts.
- **Audit Mode Selection**: Switch between **Pre-Audit** and **Post-Audit** modes.
