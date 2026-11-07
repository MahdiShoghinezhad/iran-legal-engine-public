#!/usr/bin/env bash
# Read-only, low-disclosure inventory for a self-hosted staging deployment.
# No network requests, installations, configuration changes, or secrets collection.
set -uo pipefail
say() { printf '\n[%s]\n' "$1"; }
say "Operating system"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  printf '%s\n' "${PRETTY_NAME:-unknown}"
else
  uname -s
fi
say "Architecture and CPU capacity"
uname -m
if command -v nproc >/dev/null 2>&1; then nproc; else printf 'nproc unavailable\n'; fi
say "Available memory"
if command -v free >/dev/null 2>&1; then free -h | sed -n '1,2p'; else printf 'free unavailable\n'; fi
say "Root filesystem free space"
df -hP / | sed -n '1,2p'
say "Installed runtimes (version only)"
for command_name in python3 docker nginx caddy; do
  if command -v "$command_name" >/dev/null 2>&1; then
    case "$command_name" in
      python3) python3 --version 2>&1 ;;
      docker) docker --version 2>&1 ;;
      nginx) nginx -v 2>&1 ;;
      caddy) caddy version 2>&1 | head -n 1 ;;
    esac
  else
    printf '%s: not found\n' "$command_name"
  fi
done
if command -v docker >/dev/null 2>&1; then
  say "Docker Compose availability"
  docker compose version 2>&1 || true
fi
say "Process supervisor availability"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --version | head -n 1
else
  printf 'systemctl: not found\n'
fi
say "Completed"
printf 'Read-only inventory finished. No services, ports, packages or files changed.\n'
