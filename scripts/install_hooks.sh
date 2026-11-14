#!/usr/bin/env sh
# 커밋·푸시 전에 키 패턴 검사를 자동으로 돌리는 git 훅을 설치한다.
set -e
ROOT=$(git rev-parse --show-toplevel)
for hook in pre-commit pre-push; do
  cat > "$ROOT/.git/hooks/$hook" <<'EOF'
#!/usr/bin/env sh
exec python3 "$(git rev-parse --show-toplevel)/scripts/check_secrets.py"
EOF
  chmod +x "$ROOT/.git/hooks/$hook"
done
echo "pre-commit, pre-push 훅 설치 완료"
