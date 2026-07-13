# sop-rag — Ask your messy document pile anything, get cited answers

[中文说明 →](README.zh-CN.md)

Drop **any** company documents into a folder — Word (including dirty ones with no
heading styles), PDF, Excel, legacy `.doc`, Markdown — then ask one question in
plain language. You get an answer grounded strictly in your documents, with
**precise citations whose format adapts to the source type**:

| Source | Citation |
|--------|----------|
| Word / Markdown | 【SOP-QA-001 §5.2.1 Timeline】 |
| PDF | 【SOP-TR-011 §3.2 Annual GMP Refresher (p.1)】 + clickable `file://…#page=1` |
| Excel | 【QA-LOG-2026 Sheet「偏差台账2026」rows 2–13】 |

Built for regulated environments (pharma QA/PV/CSV) where "the AI said so" is
not an acceptable source — every claim must be traceable to a controlled
document, and "not found" must be said out loud instead of guessed.

## Why this is not just another RAG demo

1. **Real-world documents are dirty.** The hard part is not the LLM — it is
   parsing a Word file where headings are just bold text, a PDF with numbered
   sections spread across pages, or an Excel deviation log. The
   `extractors/` adapter layer handles each format and degrades gracefully
   (styles → heuristics → sliding window), and every file gets a
   **parse-quality report** so bad inputs never fail silently.
2. **Cite or refuse.** The answerer may only use retrieved chunks. If they
   don't contain the answer, it says so explicitly — verified by adversarial
   tests (ask about vacation days in a GMP corpus → "not found").
3. **Incremental by content hash.** Re-ingesting is free: unchanged files
   reuse cached vectors; editing one file re-embeds only that file.
4. **Zero-touch updates (macOS).** A launchd watcher re-indexes automatically
   whenever `docs/` changes — add/edit/delete a file and the index follows.

## Architecture

```
docs/                 your document pile (mixed formats, just drop files in)
extractors/           format-adapter layer -> unified chunk structure
  __init__.py         dispatch by extension; .doc via LibreOffice; sliding-window fallback
  docx_ex.py          Heading styles if present; else heuristic titles ("5.1" numbering,
                      bold standalone lines); else sliding window
  pdf_ex.py           numbered-section chunking with page numbers; else window + pages
  xlsx_ex.py          20 rows per chunk per sheet, header carried along, row-level locators
  text_ex.py          md headings / numbered lines
ingest.py             walk docs/ -> chunk -> OpenAI text-embedding-3-small -> index/
                      (incremental: unchanged file hash -> cached vectors)
ask.py                embed question -> cosine top-6 -> Claude CLI answers from hits only
                      -> answer + 【doc locator】 citations + clickable file:// links
watch_ingest.sh       launchd-triggered auto-ingest (lock with stale-lock self-healing)
```

Unified chunk structure: `{doc_id, doc_no, doc_title, locator, breadcrumb, text}` —
retrieval and answering never know or care about the source format.

## Quick start

Requires Python 3.9+ and one [OpenAI API key](https://platform.openai.com/)
(used for both embeddings and answering; a $5 top-up lasts a long time —
indexing the demo corpus costs <$0.01 and each question ~$0.001).

```bash
git clone https://github.com/JIAOMINGMING/sop-rag.git && cd sop-rag
./install.sh        # venv + deps + guided API-key setup + first index
```

Then pick your interface:

- **Non-technical users**: double-click `start_web.command` (macOS) or run
  `.venv/bin/python web.py` — a local web page opens with a search box;
  answers show citations as clickable links (PDF jumps to the page) plus the
  retrieved source snippets. Local-only server on `127.0.0.1`; documents
  never leave the machine except LLM API calls.
- **Terminal users**:
  ```bash
  .venv/bin/python ask.py "偏差的初步评估要在几天内完成？"
  .venv/bin/python ask.py --show-hits "How many hours of annual GMP refresher training?"
  ```

Answering uses the OpenAI API by default (`SOP_RAG_CHAT_MODEL`, default
`gpt-4o-mini`). If you'd rather answer with Claude, install
[Claude Code](https://claude.com/claude-code) and set `SOP_RAG_LLM=claude` —
without an OpenAI key the `claude` CLI is used as fallback automatically.

Then replace the demo files in `docs/` with your own documents and re-run
`ingest.py` — or set up the auto-watcher:

```bash
# macOS: auto-ingest whenever docs/ changes
sed "s/YOUR_USERNAME/$USER/g" launchd/com.example.sop-rag-ingest.plist \
  > ~/Library/LaunchAgents/com.example.sop-rag-ingest.plist
launchctl load ~/Library/LaunchAgents/com.example.sop-rag-ingest.plist
```

## Prefer a recipe over a codebase? Use the Claude Code skill

This repo also ships as a **skill** — a distilled methodology that lets
Claude Code build a tailored version of this pipeline directly on *your*
documents (different formats, different citation styles, your constraints):

```bash
cp -r skill/document-rag ~/.claude/skills/
# then in Claude Code:  "Use the document-rag skill to build a Q&A index over ./my-docs"
```

See [`skill/document-rag/SKILL.md`](skill/document-rag/SKILL.md).

**Not a Claude Code user?** The skill is plain Markdown — only the
auto-discovery is Claude Code specific. Feed the same recipe to your tool of
choice:

| Tool | How |
|------|-----|
| OpenAI Codex CLI | paste SKILL.md into your project's `AGENTS.md` |
| GitHub Copilot | put it in `.github/copilot-instructions.md` |
| Cursor | put it in `.cursor/rules/` |
| Any chat AI | paste the file and say "build this pipeline over my documents" |

## Demo corpus (fictional)

10 clean SOP/WI documents of the fictional **Meridian Pharma K.K.** (PV×5,
QA×4, IT×1, docx) plus 3 deliberately dirty samples generated by
`make_test_samples.py`:

| File | Exercises |
|------|-----------|
| SOP-QC-010 (docx, Chinese) | no Heading styles, bold-as-title → heuristic chunking |
| SOP-TR-011 (PDF) | numbered-section detection + page-level citations |
| QA-LOG-2026 (xlsx) | ledger sheets → sheet + row-range citations |

Acceptance tests passed (2026-07): single-doc facts, cross-document synthesis
(deviation → CAPA chain), conditional branches (PSUR 70/90 days), adversarial
refusal, all three dirty formats, incremental re-index, regression.

## Known limitations

- Scanned PDFs (no text layer) are reported and skipped — no OCR (pluggable).
- Legacy `.doc` requires LibreOffice (`soffice`) on the machine.
- Merged Excel cells read as blanks; exotic sheet layouts may need a custom extractor.
- The auto-watcher is macOS (launchd); on Linux use `inotifywait` or cron.

## Privacy note

Documents never leave your machine except as embedding/answering API calls
(chunk text to OpenAI, retrieved snippets to Anthropic). Swap in local
embeddings + a local LLM if even that is too much for your compliance posture.

## Disclaimer

All demo documents are AI-generated fiction. Company names, document numbers
and data are invented, for RAG demonstration only — not compliance advice.
