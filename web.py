#!/usr/bin/env python3
"""本地网页界面：在浏览器里对已入库文档提问。

启动:  .venv/bin/python web.py     （或双击 start_web.command）
自动打开 http://127.0.0.1:8765。仅限本机——不对外暴露；
除 LLM API 调用外，文档不离开本机。
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse

from ask import DOCS, answer, cited_sources, retrieve

HOST, PORT = "127.0.0.1", 8765

MIME = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Document Q&A · sop-rag</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { font-family: -apple-system, "PingFang SC", "Hiragino Sans", sans-serif;
         background: #f5f6f8; color: #1c2733; padding: 40px 16px; }
  .wrap { max-width: 760px; margin: 0 auto; }
  .top { display: flex; justify-content: space-between; align-items: flex-start; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .sub { color: #667; font-size: 13px; margin-bottom: 24px; }
  .lang { font-size: 12px; color: #667; }
  .lang button { background: none; border: 0; color: #2563eb; cursor: pointer;
                 font-size: 12px; padding: 2px 4px; }
  .lang button.on { font-weight: 700; text-decoration: underline; }
  form { display: flex; gap: 8px; }
  input { flex: 1; font-size: 16px; padding: 12px 14px; border: 1px solid #cdd3da;
          border-radius: 10px; background: #fff; outline: none; }
  input:focus { border-color: #2563eb; }
  button.go { font-size: 15px; padding: 12px 22px; border: 0; border-radius: 10px;
           background: #2563eb; color: #fff; cursor: pointer; }
  button.go:disabled { background: #9db4e8; cursor: wait; }
  .card { background: #fff; border: 1px solid #e3e7ec; border-radius: 12px;
          padding: 18px 20px; margin-top: 18px; }
  #answer { white-space: pre-wrap; line-height: 1.75; font-size: 15px; }
  .lbl { font-size: 12px; color: #889; text-transform: uppercase;
         letter-spacing: .08em; margin-bottom: 10px; }
  .src a { display: inline-block; margin: 0 8px 8px 0; padding: 6px 12px;
           background: #eef2ff; color: #1d4ed8; border-radius: 8px;
           text-decoration: none; font-size: 13px; }
  .src a:hover { background: #dbe4ff; }
  details { margin-top: 10px; }
  summary { cursor: pointer; font-size: 13px; color: #667; }
  .hit { border-left: 3px solid #dde3ea; padding: 6px 12px; margin: 10px 0;
         font-size: 13px; color: #445; }
  .hit b { color: #1c2733; }
  .hit pre { white-space: pre-wrap; font-family: inherit; margin-top: 4px; }
  .err { color: #b91c1c; }
  .hidden { display: none; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1 id="h1"></h1>
    <div class="lang">
      <button id="lang-en" onclick="setLang('en')">EN</button> ·
      <button id="lang-ja" onclick="setLang('ja')">日本語</button> ·
      <button id="lang-zh" onclick="setLang('zh')">中文</button>
    </div>
  </div>
  <div class="sub" id="sub"></div>
  <form id="f">
    <input id="q" autofocus autocomplete="off">
    <button id="go" class="go" type="submit"></button>
  </form>
  <div id="out" class="card hidden">
    <div class="lbl" id="lbl-answer"></div>
    <div id="answer"></div>
    <div id="srcbox" class="hidden">
      <div class="lbl" id="lbl-sources" style="margin-top:16px"></div>
      <div class="src" id="sources"></div>
    </div>
    <details id="hitbox" class="hidden">
      <summary id="lbl-hits"></summary>
      <div id="hits"></div>
    </details>
  </div>
</div>
<script>
// 界面文案：中日英三语，可切换（EN / 日本語 / 中文）
const I18N = {
  en: {
    htmlLang: "en", title: "Document Q&A · sop-rag", h1: "📚 Document Q&A",
    sub: "Ask across all your documents, get answers with precise citations · " +
         "Data stays on your machine · One question at a time works best",
    placeholder: "e.g. How many business days for the initial OOS investigation?",
    ask: "Ask", thinking: "Thinking…",
    searching: "Retrieving and generating an answer (~10–20s)…",
    answer: "Answer", sources: "📎 Sources (click to open)",
    hits: "View retrieved source snippets", relevance: "relevance", error: "Error: ",
  },
  ja: {
    htmlLang: "ja", title: "ドキュメントQ&A · sop-rag", h1: "📚 ドキュメントQ&A",
    sub: "すべての文書を横断して質問し、正確な出典付きで回答 · " +
         "データは端末から出ません · 一度に一つの質問が最適です",
    placeholder: "例：OOSの初期調査は何営業日以内に完了する必要がありますか？",
    ask: "質問", thinking: "考え中…",
    searching: "検索して回答を生成しています（約10〜20秒）…",
    answer: "回答", sources: "📎 出典（クリックで開く）",
    hits: "検索でヒットした原文の抜粋を見る", relevance: "関連度", error: "エラー：",
  },
  zh: {
    htmlLang: "zh", title: "文档问答 · sop-rag", h1: "📚 文档问答",
    sub: "跨全部文档提问，回答带精确出处 · 数据不离开本机 · 一次问一个问题效果最好",
    placeholder: "例如：偏差的初步评估要在几天内完成？",
    ask: "提问", thinking: "思考中…",
    searching: "正在检索并生成回答（约 10～20 秒）…",
    answer: "回答", sources: "📎 原文（点击打开）",
    hits: "查看检索命中的原文片段", relevance: "相关度", error: "出错了：",
  },
};
const STORED = localStorage.getItem("sop_rag_lang");
function detectLang() {
  const l = (navigator.language || "en").toLowerCase();
  if (l.startsWith("zh")) return "zh";
  if (l.startsWith("ja")) return "ja";
  return "en";
}
let LANG = STORED || detectLang();
if (!I18N[LANG]) LANG = "en";

function t() { return I18N[LANG]; }
function setLang(lang) {
  LANG = I18N[lang] ? lang : "en";
  localStorage.setItem("sop_rag_lang", LANG);
  const x = t();
  document.documentElement.lang = x.htmlLang;
  document.title = x.title;
  document.getElementById("h1").textContent = x.h1;
  document.getElementById("sub").textContent = x.sub;
  document.getElementById("q").placeholder = x.placeholder;
  document.getElementById("go").textContent = x.ask;
  document.getElementById("lbl-answer").textContent = x.answer;
  document.getElementById("lbl-sources").textContent = x.sources;
  document.getElementById("lbl-hits").textContent = x.hits;
  document.getElementById("lang-en").classList.toggle("on", LANG === "en");
  document.getElementById("lang-ja").classList.toggle("on", LANG === "ja");
  document.getElementById("lang-zh").classList.toggle("on", LANG === "zh");
  // 切换语言时清空上一次的提问与回答，避免残留另一种语言的内容
  document.getElementById("q").value = "";
  document.getElementById("out").classList.add("hidden");
  document.getElementById("answer").textContent = "";
}
setLang(LANG);

const f = document.getElementById("f"), q = document.getElementById("q"),
      go = document.getElementById("go"), out = document.getElementById("out"),
      ans = document.getElementById("answer");
f.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = q.value.trim();
  if (!question) return;
  go.disabled = true; go.textContent = t().thinking;
  out.classList.remove("hidden");
  ans.textContent = t().searching; ans.classList.remove("err");
  document.getElementById("srcbox").classList.add("hidden");
  document.getElementById("hitbox").classList.add("hidden");
  try {
    const r = await fetch("/api/ask", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question})});
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    ans.textContent = d.answer;
    const sb = document.getElementById("sources");
    sb.innerHTML = "";
    for (const s of d.sources) {
      const a = document.createElement("a");
      a.href = s.url; a.target = "_blank"; a.textContent = s.label;
      sb.appendChild(a);
    }
    document.getElementById("srcbox").classList.toggle("hidden", !d.sources.length);
    const hb = document.getElementById("hits");
    hb.innerHTML = "";
    for (const h of d.hits) {
      const div = document.createElement("div");
      div.className = "hit";
      const b = document.createElement("b");
      b.textContent = `${h.doc_no} ${h.locator}（${t().relevance} ${h.score.toFixed(3)}）`;
      const pre = document.createElement("pre");
      pre.textContent = h.text;
      div.append(b, pre);
      hb.appendChild(div);
    }
    document.getElementById("hitbox").classList.toggle("hidden", !d.hits.length);
  } catch (err) {
    ans.textContent = t().error + err.message; ans.classList.add("err");
  } finally {
    go.disabled = false; go.textContent = t().ask;
  }
});
</script>
</body>
</html>"""


def web_sources(answer_text, hits):
    out = []
    for doc_no, doc_id, page in cited_sources(answer_text, hits):
        url = "/doc/" + quote(doc_id)
        label = doc_no
        if page:
            url += f"#page={page}"
            label += f" (p.{page})"
        out.append({"label": label, "url": url})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, PAGE)
        if path.startswith("/doc/"):
            name = unquote(path[len("/doc/"):])
            f = (DOCS / name).resolve()
            if f.parent != DOCS.resolve() or not f.is_file():
                return self._send(404, "not found", "text/plain")
            ctype = MIME.get(f.suffix.lower(), "application/octet-stream")
            extra = {}
            if ctype == "application/octet-stream":
                # Word/Excel：浏览器下载文件，在本地打开
                extra["Content-Disposition"] = \
                    f"attachment; filename*=UTF-8''{quote(f.name)}"
            return self._send(200, f.read_bytes(), ctype, extra)
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/ask":
            return self._send(404, "not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length", 0))
            question = json.loads(self.rfile.read(n))["question"].strip()
            if not question:
                return self._send(400, "empty question", "text/plain")
            hits = retrieve(question)
            text = answer(question, hits)
            payload = {
                "answer": text,
                "sources": web_sources(text, hits),
                "hits": [{"score": s, "doc_no": c["doc_no"],
                          "locator": c["locator"], "text": c["text"][:400]}
                         for s, c in hits],
            }
            self._send(200, json.dumps(payload, ensure_ascii=False),
                       "application/json; charset=utf-8")
        except Exception as e:
            self._send(500, f"{type(e).__name__}: {e}", "text/plain; charset=utf-8")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"文档问答已启动: {url}  （关闭本窗口即停止）")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
