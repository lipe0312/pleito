#!/usr/bin/env bash
set -uo pipefail

DRY=""; [ "${1:-}" = "--dry-run" ] && DRY=1
ROOT="$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
cd "$ROOT" || exit 1
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
run() { if [ -n "$DRY" ]; then echo "  (dry) $*"; else "$@" >/dev/null 2>&1; fi; }

pr_state() { gh api "repos/$REPO/pulls?state=all&head=${REPO%%/*}:$1" --jq '.[0] | if . == null then "" elif .merged_at then "MERGED" else (.state | ascii_upcase) end' 2>/dev/null; }

git fetch -q origin --prune 2>/dev/null

git worktree list --porcelain | awk '
  /^worktree /{wt=$2; br=""; lk=0}
  /^branch /{br=$2; sub("refs/heads/","",br)}
  /^locked/{lk=1}
  /^$/{ if (wt ~ /\/\.claude\/worktrees\//) print wt "\t" br "\t" lk }
  END{ if (wt ~ /\/\.claude\/worktrees\//) print wt "\t" br "\t" lk }' | sort -u |
while IFS="$(printf '\t')" read -r wt br lk; do
  [ -z "$wt" ] && continue
  if [ "$lk" = "1" ]; then echo "mantido (sessao viva): $wt"; continue; fi
  st="$(pr_state "$br")"
  case "$st" in
    MERGED|CLOSED)
      echo "worktree $st: $wt ($br) -> pasta e branch apagadas"
      run git worktree remove --force "$wt"
      run git branch -D "$br"
      ;;
    *) echo "mantido ($([ -n "$st" ] && echo "PR $st" || echo "sem PR")): $wt" ;;
  esac
done
git worktree prune

for br in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
  [ "$br" = "main" ] && continue
  git worktree list --porcelain | /usr/bin/grep -q "^branch refs/heads/$br$" && continue
  case "$br" in
    worktree-*) echo "branch orfa do claude -w: $br -> apagada"; run git branch -D "$br"; continue ;;
  esac
  st="$(pr_state "$br")"
  if [ "$st" = "MERGED" ] || [ "$st" = "CLOSED" ]; then
    echo "branch $st: $br -> apagada (local e remota)"
    run git branch -D "$br"
    run git push origin --delete "$br"
  fi
done

for rb in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/ | sed 's#^origin/##'); do
  case "$rb" in main|HEAD|origin) continue ;; esac
  st="$(pr_state "$rb")"
  if [ "$st" = "MERGED" ] || [ "$st" = "CLOSED" ]; then
    echo "remota $st: $rb -> apagada"; run git push origin --delete "$rb"
  fi
done

for f in .claude/preview/*.html /tmp/pleito-*.log /tmp/pleito-*.md; do
  [ -e "$f" ] || continue
  n="$(basename "$f" | /usr/bin/grep -oE '^(pleito-)?[0-9]+' | /usr/bin/grep -oE '[0-9]+')"
  [ -z "$n" ] && continue
  if [ "$(gh api "repos/$REPO/issues/$n" --jq .state 2>/dev/null)" = "closed" ]; then
    echo "arquivo da issue fechada #$n: $f -> apagado"; run rm -f "$f"
  fi
done

if [ "$(git branch --show-current)" = "main" ] && [ -z "$(git status --porcelain)" ]; then
  run git merge --ff-only -q origin/main
fi
echo "faxina ok"
