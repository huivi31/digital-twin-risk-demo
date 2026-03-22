# CHANGELOG

## v2.4.0 - 2026-03-22

### 新增功能

- **资料投喂功能**: 
  - 增加了 `/feed/materials` API，支持手动投喂攻击材料。
  - 增加了 `/feed/slang` API，支持手动投喂行业黑话/暗语。
  - 增加了 `/feed/cases` API，支持手动投喂绕过案例 (Badcase)。
  - 增加了 `/knowledge/status` API，用于获取知识库状态。
  - `attack_knowledge.py` 中的 `KnowledgeStore` 类新增 `feed_materials`, `feed_slang`, `feed_cases` 方法，用于管理投喂资料。

### 改进与优化

- **代码修复**: 修复了 `web_app.py` 中 `KNOWLEDGE_STORE.dlear()` 的拼写错误，更正为 `KNOWLEDGE_STORE.clear()`。
- **版本管理**: 在 `README.md` 中更新了版本号至 `v2.4.0`，并增加了资料投喂功能的详细说明。

### 其他

- 项目代码已整理，并修复了已知问题。
