# v2 对照审计报告 (2026-09-03)

参照 `C:\Users\12164\Desktop\记忆.docx`（主流 Agent Harness Memory 对比：Claude Code / Codex / OpenClaw）对 v2 三层记忆做全面对照审计。

## 审计结论：已符合项（不动）

| 文档原则 | v2 对应实现 |
|---|---|
| Codex NO-OP 门控（没有值得记的就不记） | organize "NO-OP" / compress "ALREADY-COMPACT" |
| 原始证据不可变（raw rollouts immutable） | 整理/压缩只读 `store.items`，永不回写 |
| "过滤而非槽位"（用户要求）+ OpenClaw 反例（非LLM做整合质量差） | 保存层只做"删除"（去重/纯应答/样板话），**宁可漏删不可误删**；整合全部交给 LLM 层 |
| 高信号筛选（Codex 四类高价值桶） | compress 的"高区分度信息"原则同源 |
| 纠正关系标注 | organize "之前X→现已纠正为Y" |
| 快慢记忆混合（文档总评建议） | 保存=快（实时本地），整理/压缩=慢（手动触发） |

## 审计发现的差距与修复（4 项）

1. **敏感信息脱敏缺失**（Codex: never store tokens/keys → `[REDACTED_SECRET]`）
   → 保存层入库前本地正则脱敏：API key / 密码 / 手机号 / 身份证。
   修复中发现并解决：`\b` 在中文语境失效（汉字是 `\w`），改用 `(?<!\d)…(?!\d)` 数字环视。
2. **召回缺时效与信任标注**（Claude: >1天记忆附"某时刻观察"；Codex: 从记忆作答须声明可能过时）
   → `default_memory_block` 统一附"截至第N轮+可能过时+冲突以当前为准+无则明说不知道"。
   server 快照新增 `best_block`，前端默认 builder 改用它。
3. **来源轮次在整理/压缩后丢失**（Claude evidence 原则；v1 已踩过无来源的坑）
   → organize/compress prompt 要求保留 `[T#]` 标记。回归实测：压缩后仍带 `[T1]/[T2]`。
4. **审计记录**：`_ACK_WORDS` 硬编码词表与 OpenClaw"硬编码小术语表"反例形似，但定位不同——OpenClaw 用术语表做召回匹配（影响正确性），我们只用于"删除纯客套"且默认保留（漏删无害）。保留设计，此处注明风险。

## 文档中有意不采纳的

- **向量/RAG 召回**（OpenClaw 式）：单学生辅导记忆量小，全量注入即可；文档也指出 RAG 在此类场景"过誉回归正常"。
- **Dream 式异步整合**：用户已指定手动按钮触发，更符合教学场景可控性。
- **用户主动编辑入口**（Codex ad_hoc notes）：需求未提，留作后续。

## 回归验证

脱敏单测 3/3（key/手机/身份证/密码）；E2E 2 轮对话 + 整理 + 压缩通过；`best_block` 含信任标注；整理/压缩文档保留 `[T#]`。
