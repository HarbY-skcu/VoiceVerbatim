#!/bin/bash
# Claude Code status line: git branch, tokens used/limit, rate limits, model name

input=$(cat)

read_fields=$(python3 -c '
import json, sys
d = json.load(sys.stdin)
model = d.get("model", {}).get("display_name", "")
cwd = d.get("workspace", {}).get("current_dir", "")
ctx = d.get("context_window", {}) or {}
input_tokens = ctx.get("total_input_tokens", 0) or 0
output_tokens = ctx.get("total_output_tokens", 0) or 0
context_limit = ctx.get("context_window_size", "")
rl = d.get("rate_limits", {}) or {}
five = rl.get("five_hour", {}).get("used_percentage", "")
week = rl.get("seven_day", {}).get("used_percentage", "")
print(model)
print(cwd)
print(input_tokens)
print(output_tokens)
print(context_limit)
print(five)
print(week)
' <<< "$input")

model=$(sed -n '1p' <<< "$read_fields")
cwd=$(sed -n '2p' <<< "$read_fields")
input_tokens=$(sed -n '3p' <<< "$read_fields")
output_tokens=$(sed -n '4p' <<< "$read_fields")
context_limit=$(sed -n '5p' <<< "$read_fields")
five=$(sed -n '6p' <<< "$read_fields")
week=$(sed -n '7p' <<< "$read_fields")

# Git branch (skip optional locks for speed/safety)
branch=""
if [ -n "$cwd" ] && git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null)
fi

total_tokens=$((input_tokens + output_tokens))

# Format tokens as human readable (e.g. 12.3k)
fmt_k() {
  if [ "$1" -ge 1000 ] 2>/dev/null; then
    awk -v t="$1" 'BEGIN { printf "%.1fk", t/1000 }'
  else
    echo "$1"
  fi
}
tokens_fmt=$(fmt_k "$total_tokens")
if [ -n "$context_limit" ]; then
  limit_fmt=$(fmt_k "$context_limit")
  tokens_fmt="${tokens_fmt}/${limit_fmt}"
fi

# Rate limits
rate_out=""
[ -n "$five" ] && rate_out="5h:$(printf '%.0f' "$five")%"
if [ -n "$week" ]; then
  week_fmt="7d:$(printf '%.0f' "$week")%"
  if [ -n "$rate_out" ]; then
    rate_out="$rate_out $week_fmt"
  else
    rate_out="$week_fmt"
  fi
fi

# Colors (dimmed, terminal-friendly)
COLOR_BRANCH='\033[2;32m'   # dim green
COLOR_TOKENS='\033[2;36m'   # dim cyan
COLOR_RATE='\033[2;33m'     # dim yellow
COLOR_MODEL='\033[2;35m'    # dim magenta
RESET='\033[0m'
SEP='\033[2;37m|\033[0m'

parts=()
[ -n "$branch" ] && parts+=("$(printf "${COLOR_BRANCH}%s${RESET}" "$branch")")
parts+=("$(printf "${COLOR_TOKENS}tokens:%s${RESET}" "$tokens_fmt")")
[ -n "$rate_out" ] && parts+=("$(printf "${COLOR_RATE}%s${RESET}" "$rate_out")")
parts+=("$(printf "${COLOR_MODEL}%s${RESET}" "$model")")

out=""
for i in "${!parts[@]}"; do
  if [ "$i" -eq 0 ]; then
    out="${parts[$i]}"
  else
    out="$out $(printf "$SEP") ${parts[$i]}"
  fi
done

printf "%b\n" "$out"
