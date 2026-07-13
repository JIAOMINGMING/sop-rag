#!/bin/bash
# 双击启动文档问答网页（macOS）。关闭这个窗口即停止服务。
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "还没安装：请先运行 ./install.sh"
  read -r -p "按回车退出"
  exit 1
fi
exec ./.venv/bin/python web.py
