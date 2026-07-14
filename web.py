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
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>文档问答 · sop-rag</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { font-family: -apple-system, "PingFang SC", "Hiragino Sans", sans-serif;
         background: #f5f6f8; color: #1c2733; padding: 40px 16px; }
  .wrap { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .sub { color: #667; font-size: 13px; margin-bottom: 24px; }
  form { display: flex; gap: 8px; }
  input { flex: 1; font-size: 16px; padding: 12px 14px; border: 1px solid #cdd3da;
          border-radius: 10px; background: #fff; outline: none; }
  input:focus { border-color: #2563eb; }
  button { font-size: 15px; padding: 12px 22px; border: 0; border-radius: 10px;
           background: #2563eb; color: #fff; cursor: pointer; }
  button:disabled { background: #9db4e8; cursor: wait; }
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
  <h1>📚 文档问答</h1>
  <div class="sub">跨全部文档提问，回答带精确出处 · 数据不离开本机 · 一次问一个问题效果最好</div>
  <form id="f">
    <input id="q" placeholder="例如：偏差的初步评估要在几天内完成？" autofocus autocomplete="off">
    <button id="go" type="submit">提问</button>
  </form>
  <div id="out" class="card hidden">
    <div class="lbl">回答</div>
    <div id="answer"></div>
    <div id="srcbox" class="hidden">
      <div class="lbl" style="margin-top:16px">📎 原文（点击打开）</div>
      <div class="src" id="sources"></div>
    </div>
    <details id="hitbox" class="hidden">
      <summary>查看检索命中的原文片段</summary>
      <div id="hits"></div>
    </details>
  </div>
</div>
<script>
const f = document.getElementById("f"), q = document.getElementById("q"),
      go = document.getElementById("go"), out = document.getElementById("out"),
      ans = document.getElementById("answer");
f.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = q.value.trim();
  if (!question) return;
  go.disabled = true; go.textContent = "思考中…";
  out.classList.remove("hidden");
  ans.textContent = "正在检索并生成回答（约 10～20 秒）…"; ans.classList.remove("err");
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
      b.textContent = `${h.doc_no} ${h.locator}（相关度 ${h.score.toFixed(3)}）`;
      const pre = document.createElement("pre");
      pre.textContent = h.text;
      div.append(b, pre);
      hb.appendChild(div);
    }
    document.getElementById("hitbox").classList.toggle("hidden", !d.hits.length);
  } catch (err) {
    ans.textContent = "出错了：" + err.message; ans.classList.add("err");
  } finally {
    go.disabled = false; go.textContent = "提问";
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
