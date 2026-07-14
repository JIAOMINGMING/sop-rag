---
name: document-rag
description: Build a cited Q&A (RAG) pipeline over a folder of mixed real-world documents (Word/PDF/Excel/legacy .doc/Markdown) — ask one question across all documents, get an answer with format-adaptive citations (§section / p.page / sheet+rows) and cite-or-refuse behavior. Use when the user wants to "ask questions across my documents/SOPs/manuals", "build a knowledge base over these files", or "RAG with sources/citations".
---

# document-rag — a recipe for cited Q&A over messy document piles

> **Portability note**: the frontmatter above and auto-triggering are Claude
> Code conventions (`cp -r` this folder into `~/.claude/skills/`). The recipe
> itself is plain Markdown — Codex CLI users can paste it into `AGENTS.md`,
> Copilot users into `.github/copilot-instructions.md`, Cursor users into
> `.cursor/rules/`, or hand it to any capable AI directly.

You are building a small, auditable RAG pipeline for the user's own documents.
Reference implementation: https://github.com/JIAOMINGMING/sop-rag (read it if
reachable, but adapt to the user's documents rather than copying blindly).

## Core design rules (do not compromise these)

1. **Format-adapter layer with graceful degradation.** One extractor per
   format, all returning the SAME chunk shape:
   `{doc_id, doc_no, doc_title, locator, breadcrumb, text}`.
   Retrieval and answering must never know the source format.
   - **docx**: use Heading styles if present; else heuristics — numbered lines
     (`^\d+(\.\d+)*[.\s]`) or short bold standalone paragraphs as titles; else
     sliding window (~1200 chars, ~200 overlap, break at newlines).
   - **PDF**: detect numbered section headings across lines; locators always
     carry page numbers (`§3.2 Title (p.4)`). No text layer → report
     "scanned PDF, needs OCR" and skip (or wire OCR if the user asks).
   - **Excel**: chunk each sheet ~20 rows at a time, repeat the header row in
     every chunk, locator = `Sheet「name」rows N–M`.
   - **Legacy .doc**: convert via LibreOffice `soffice --headless
     --convert-to docx`; if unavailable, report and skip.
   - **md/txt**: split on headings / numbered lines.
2. **Parse-quality report.** After ingest, print per file: parse mode
   (styles / heuristic / sections / sliding-window / sheet-rows / cached /
   FAILED) + chunk count + warnings. One bad file must never kill the run or
   be swallowed silently.
3. **Incremental indexing by content hash.** Store `{filename: sha256}` in a
   manifest; unchanged files reuse cached vectors. Deleting a file removes its
   chunks on the next run.
4. **Cite or refuse.** The answer prompt must (a) forbid knowledge outside the
   retrieved chunks, (b) require a 【doc_no locator】 citation after every
   claim, copied verbatim from the chunk header, (c) require an explicit
   "not found in the provided documents" when retrieval doesn't cover the
   question. Never let it guess.
5. **Clickable sources.** Map cited doc_nos back to files and print `file://`
   URIs (use `Path.as_uri()` for correct percent-encoding); append `#page=N`
   for PDFs. Word/Excel can only link to the file itself — say so.

## Default stack (swap on request)

- Embeddings: OpenAI `text-embedding-3-small`, batched, L2-normalized,
  stored as a numpy matrix + `chunks.json` — no vector DB needed below ~100k
  chunks; cosine = one matrix-vector product.
- Embedding input: prefix each chunk with `[doc_no doc_title] breadcrumb` so
  document identity is searchable.
- Retrieval: cosine top-6.
- Answering: `claude -p` CLI (or the user's preferred LLM API), temperature
  low. **Answer in the question's language, and force it in code.** A prompt
  written entirely in one language biases the model to reply in that language
  even when the user asked in another — detect the question's script
  (CJK / kana / Latin) and append an explicit directive ("The question is in
  English — write the ENTIRE answer in English, including the sources line;
  keep 【…】 markers verbatim"). Give the not-found refusal and the "Sources:"
  label in each supported language too.
- Privacy-sensitive users: offer local embeddings (e.g. sentence-transformers)
  + a local LLM; the architecture is unchanged.

## Optional: zero-touch folder watching

- macOS: launchd `WatchPaths` on `docs/` → a shell script that takes an
  `mkdir` lock (self-heal locks older than 5 min; WAIT for the lock rather
  than exit, so changes during a running ingest aren't lost), sleeps ~5 s for
  copies to finish, then runs ingest and appends to a log.
- Linux: `inotifywait -m` or a cron entry running the incremental ingest.

## Build order (adapt to what the user actually has)

1. Look at the user's real files first — list formats, open a few, note how
   headings/structure actually appear. Choose extractors accordingly.
2. Build ingest + extractors; run; show the user the parse-quality report and
   fix the worst parses before touching retrieval.
3. Build ask; verify citations point where they claim (spot-check 2–3).
4. Acceptance tests, all four kinds: single-doc fact, cross-document
   synthesis, conditional branch (a question whose answer depends on a case
   distinction), and an adversarial question whose answer is NOT in the corpus
   (must refuse, not hallucinate).
5. Only then add conveniences (watcher, clickable links).

## Pitfalls learned the hard way

- Word autosave temp files (`~$…`) must be excluded from ingest.
- Merged Excel cells read as blanks — warn, don't crash.
- Combined multi-topic questions skew the embedding; suggest users ask one
  question at a time.
- If the answering CLI hits a usage limit it may exit in ~2 s with a limit
  message on stdout — surface that error; do not present it as "not found".
- Cross-lingual retrieval is weak on a single-language corpus: a question in
  language A over documents written only in language B may not rank the right
  chunk into top-k, so the answer wrongly refuses. Forcing the answer language
  (above) does not fix retrieval — tell users to query in the corpus language,
  or translate/expand the query before embedding, if cross-lingual recall matters.
- A multilingual UI must clear the question box and previous answer when the
  language toggle changes — stale text in another language looks broken.
