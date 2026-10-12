# references/ 留档说明

## 记忆_extracted.txt（2026-09-03 自 `C:\Users\12164\Desktop\记忆.docx` 全文提取，105,666 字符 / 820 段）

用户提供的记忆机制调研资料原文，含 **Claude Code 与 Codex 两套记忆机制的完整实现提示词**及 OpenClaw 反例分析。是本项目三层记忆（v2）与记忆风格流派（memory_styles.py）的设计依据。

要点索引：
- **Codex**：两阶段挖掘、NO-OP 门控、渐进披露（dense / navigational / discriminative）、`memory_summary.md`、脱敏 `[REDACTED_SECRET]`（"memory_summary.md" 出现 40 处，含多段完整提示词）
- **Claude Code**：索引+条目、召回怀疑、时效提醒、Dream 异步整合
- **OpenClaw**：非 LLM 整合的反例（术语表硬编码召回，质量差）
- 番外：记忆堆积→可塑性丧失

⚠ 使用纪律：v2 现行提示词（memory_core.py / memory_styles.py）是**依据本文档转述改写**的版本，非逐字原版；如需对照原版提示词，以此文件为准。原件 docx 在桌面，本文件为项目内归档副本，请勿删改（如需修订请新增版本文件）。
