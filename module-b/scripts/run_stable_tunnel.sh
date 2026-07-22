#!/usr/bin/env bash
# 稳定入口：launchd 守护本地 Agent + frpc，ECS systemd 守护 frps。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UID_NUM="$(id -u)"
LOCAL_URL="http://127.0.0.1:8002"
PUBLIC_URL="http://123.56.100.219"
API_PLIST="$HOME/Library/LaunchAgents/com.indusmind.agent-api.plist"
FRPC_PLIST="$HOME/Library/LaunchAgents/com.indusmind.frpc.plist"

ensure_service() {
  local label="$1"
  local plist="$2"
  if ! launchctl print "gui/${UID_NUM}/${label}" >/dev/null 2>&1; then
    launchctl bootstrap "gui/${UID_NUM}" "$plist"
  fi
  launchctl enable "gui/${UID_NUM}/${label}"
  if [[ "$(launchctl print "gui/${UID_NUM}/${label}")" != *"state = running"* ]]; then
    launchctl kickstart "gui/${UID_NUM}/${label}"
  fi
}

wait_health() {
  local url="$1"
  for _ in $(seq 1 30); do
    if curl -fsS -m 2 "${url}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

ensure_service "com.indusmind.agent-api" "$API_PLIST"
ensure_service "com.indusmind.frpc" "$FRPC_PLIST"

if ! wait_health "$LOCAL_URL"; then
  launchctl kickstart -k "gui/${UID_NUM}/com.indusmind.agent-api"
  wait_health "$LOCAL_URL" || {
    echo "本地 Agent 不可用，请检查 ${ROOT}/.logs/agent-api.log" >&2
    exit 1
  }
fi

if ! wait_health "$PUBLIC_URL"; then
  launchctl kickstart -k "gui/${UID_NUM}/com.indusmind.frpc"
  wait_health "$PUBLIC_URL" || {
    echo "固定公网入口不可用，请检查 ${ROOT}/.logs/frpc.log" >&2
    exit 1
  }
fi

echo "本地 Agent: $(curl -fsS -m 5 "${LOCAL_URL}/health")"
echo "固定公网入口: $(curl -fsS -m 15 "${PUBLIC_URL}/health")"
echo "Base URL: ${PUBLIC_URL}"
echo "launchd 会在进程退出和用户登录后自动重启 Agent/frpc。"
