# SOP 多文档检索知识库（RAG）

[English README →](README.md)

问一句话，跨全部公司文档找答案，并标注精确出处。**不限文档类型**：Word（含无标题样式的脏文档）、PDF、Excel、老 .doc、Markdown、txt 都能进库，出处格式随文档类型自适应：

- Word / md：`【SOP-QA-001 §5.2.1 Timeline】`
- PDF：`【SOP-TR-011 §3.2 Annual GMP Refresher (p.1)】`
- Excel：`【QA-LOG-2026 Sheet「偏差台账2026」行2-13】`

## 架构

```
docs/                 文档库（混合格式，直接丢文件进来即可）
extractors/           格式适配层 —— 各格式解析成统一 chunk 结构
  __init__.py         按扩展名分发；.doc 经 LibreOffice 转换；滑窗兜底
  docx_ex.py          有 Heading 样式按样式切；没有则启发式识别标题
                      （"5.1"编号模式 / 加粗独立短行）；再不行滑窗
  pdf_ex.py           识别编号章节则按章节切（带页码）；否则滑窗+页码
  xlsx_ex.py          每 sheet 按 20 行一块，表头随块携带，定位到行号
  text_ex.py          md 标题 / 编号行切分
ingest.py             遍历 docs/ → 切分 → OpenAI text-embedding-3-small
                      → index/（增量：文件 hash 不变直接复用缓存向量）
ask.py                问题向量化 → 余弦 top-6 → claude CLI 基于命中片段作答
                      → 中文回答 + 【文档编号 定位】出处，答不到明说
```

统一 chunk 结构：`{doc_id, doc_no, doc_title, locator, breadcrumb, text}`——检索和作答层完全不感知源格式。

## 使用

```bash
# 把任意文档丢进 docs/ 即可 —— launchd 监听到变化后自动增量 ingest
# （也可手动跑：.venv/bin/python ingest.py，只向量化新增/修改的文件）

# 提问
.venv/bin/python ask.py "偏差的初步评估要在几天内完成？"
.venv/bin/python ask.py --show-hits "..."   # 同时显示检索命中
```

OPENAI_API_KEY 从环境变量或 `~/learning-plan/coach/config.sh` 自动读取。

### docs/ 自动监听

`~/Library/LaunchAgents/com.jiaoming.sop-rag-ingest.plist`（WatchPaths）监听 `docs/`，
增删改文件后自动跑 `watch_ingest.sh` → `ingest.py`，日志在 `logs/watch_ingest.log`。
mkdir 锁 + >5 分钟孤儿锁自愈；拿不到锁会等待重试，避免漏掉 ingest 进行中的新变更。

### 出处链接

回答末尾附「📎 原文链接」：把引用的【文档编号 …】映射为可点击的 `file://` 链接
（终端 Cmd+点击打开），PDF 带 `#page=N` 可直落到页；Word/Excel 只能打开文件本身，
章节/行号需按出处文字自行定位。

## 解析质量报告

ingest 结束打印每份文件：解析方式（styles / heuristic / sections / sliding-window / sheet-rows / cached）+ chunk 数 + 警告（如"未识别出标题结构，退化为滑窗切分"、"扫描版 PDF 需要 OCR，已跳过"）。脏文件不会静默吞掉。

## 文档库内容（虚构公司 Meridian Pharma K.K.，仅供 Demo）

10 份干净 SOP/WI（PV×5 / QA×4 / IT×1，docx）+ 3 份故意制造的脏样本：

| 文件 | 用来验证 |
|------|---------|
| SOP-QC-010_OOS调查.docx | 中文、无 Heading 样式、纯加粗当标题 → heuristic 切分 |
| SOP-TR-011_Training_Management.pdf | PDF 编号章节识别 + 页码出处 |
| QA-LOG-2026_偏差台账.xlsx | Excel 台账 → sheet+行号出处 |

脏样本由 `make_test_samples.py` 生成；干净 SOP 源稿在 `src/*.md`，`build_docx.py` 转 Word。

## 验收记录

**2026-07-11 v1（10 份干净 docx）**：单文档事实 / 跨文档综合（偏差→CAPA 链）/ 条件分支（PSUR 70/90 天）/ 反向测试（问年假→明确说未找到）全部通过。

**2026-07-11 v2（多格式改造后）**：
- ✅ 脏 Word：OOS 初步调查 3 个工作日、扩展调查 20 个工作日【SOP-QC-010 §4.1/§4.2】
- ✅ PDF：年度 GMP 再培训 ≥8 学时【SOP-TR-011 §3.2 (p.1)】
- ✅ Excel：2 条 Critical 偏差及状态【QA-LOG-2026 Sheet「偏差台账2026」行2-13】
- ✅ 增量索引：二次 ingest 全缓存复用（0 新向量化）；改 1 份文件只重建该文件
- ✅ 回归：原 docx 问答不受影响

## 已知边界

- 扫描版 PDF（无文字层）目前标记跳过，不做 OCR——需要时可接 OCR 兜底
- .doc 依赖本机 LibreOffice（soffice），未安装则报告跳过
- Excel 合并单元格读出来为空值，复杂报表格式可能需要按 sheet 定制

## 免责声明

全部文档为 AI 生成的虚构内容，公司、编号、数据均为虚构，仅用于 RAG 技术演示，不构成任何合规建议。
