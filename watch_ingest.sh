#!/bin/bash
# docs/ 有变化时由 launchd WatchPaths 触发：自动增量重建索引。
# 手动测试: bash watch_ingest.sh
set -u
ROOT="$HOME/sop-rag"
LOG_DIR="$ROOT/logs"
LOG="$LOG_DIR/watch_ingest.log"
LOCK="$ROOT/.ingest.lock"
mkdir -p "$LOG_DIR"

# mkdir 锁；残留超过 5 分钟视为孤儿锁自愈。拿不到锁时等待而不是退出，
# 避免"ingest 进行中又来了新文件"这次变更被漏掉。
acquired=0
i=0
while [ $i -lt 24 ]; do
  if mkdir "$LOCK" 2>/dev/null; then
    acquired=1
    break
  fi
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +5 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null
  else
    sleep 5
  fi
  i=$((i + 1))
done
if [ $acquired -ne 1 ]; then
  echo "$(date '+%F %T') 等锁超时，放弃本次触发" >> "$LOG"
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

sleep 5   # 等文件拷贝/保存写完再开始解析

{
  echo "=== $(date '+%F %T') docs/ 变化，自动 ingest ==="
  "$ROOT/.venv/bin/python" "$ROOT/ingest.py" 2>&1
  echo ""
} >> "$LOG"
