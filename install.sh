#!/bin/bash
# 一键安装：只需要装好 Python 3 和一个 OpenAI API key。
# 用法: ./install.sh
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "❌ 未找到 python3，请先安装 Python 3（https://www.python.org/downloads/）"
  exit 1
fi

echo "① 创建虚拟环境并安装依赖…"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -f .env ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "② 需要一个 OpenAI API key（platform.openai.com → API keys，充值 \$5 可用很久）"
  read -r -p "   请粘贴你的 key（sk-…）: " key
  echo "OPENAI_API_KEY=${key}" > .env
  echo "   已保存到 .env（此文件不会被 git 提交）"
else
  echo "② 已检测到 API key，跳过"
fi

echo "③ 首次建立索引…"
.venv/bin/python ingest.py

echo ""
echo "✅ 安装完成！两种用法："
echo "   · 双击 start_web.command → 浏览器里提问（推荐）"
echo "   · 终端: .venv/bin/python ask.py \"你的问题\""
echo "   把你自己的文档放进 docs/ 后重跑 .venv/bin/python ingest.py 即可换库"
