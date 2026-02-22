#!/bin/bash
# deploy_to_ec2.sh
# ローカルから EC2 本番環境に Git 経由でデプロイするスクリプト
#
# 使い方:
#   ./scripts/deploy_to_ec2.sh
#
# 前提:
#   - EC2 上に /home/ubuntu/NewFUHI が git clone 済み
#   - EC2 上に venv が作成済み
#   - SSH 鍵が ~/.ssh/newfuhi-key.pem に存在
#   - EC2 の GitHub にアクセス可能（HTTPS clone or deploy key）

set -e

# ========== 設定 ==========
EC2_HOST="52.198.72.13"
EC2_USER="ubuntu"
SSH_KEY="$(dirname "$0")/../newfuhi-key.pem"
REMOTE_PATH="/home/ubuntu/NewFUHI"
BRANCH="main"

# 色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# SSH コマンド
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $EC2_USER@$EC2_HOST"

echo ""
echo "========================================"
echo "  NewFUHI EC2 Production Deploy"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# ========== Step 1: ローカルの変更を push ==========
echo -e "${GREEN}[1/5] ローカルの変更を GitHub に push...${NC}"
cd "$(dirname "$0")/.."

CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo -e "${YELLOW}  現在のブランチ: $CURRENT_BRANCH (デプロイ対象: $BRANCH)${NC}"
    echo -e "${YELLOW}  $BRANCH ブランチに切り替えてから実行してください${NC}"
    exit 1
fi

# 未コミットの変更チェック
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${YELLOW}  未コミットの変更があります。先にコミットしてください。${NC}"
    git status --short
    exit 1
fi

git push origin $BRANCH
echo -e "${GREEN}  push 完了${NC}"
echo ""

# ========== Step 2: EC2 で git pull ==========
echo -e "${GREEN}[2/5] EC2 で git pull...${NC}"
$SSH_CMD "cd $REMOTE_PATH && git fetch origin && git reset --hard origin/$BRANCH"
echo -e "${GREEN}  pull 完了${NC}"
echo ""

# ========== Step 3: 依存関係インストール & マイグレーション ==========
echo -e "${GREEN}[3/5] 依存関係 & マイグレーション...${NC}"
$SSH_CMD "cd $REMOTE_PATH && \
    source venv/bin/activate && \
    pip install -q -r requirements.txt && \
    DJANGO_SETTINGS_MODULE=project.settings python manage.py migrate --noinput && \
    DJANGO_SETTINGS_MODULE=project.settings python manage.py collectstatic --noinput"
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 4: Gunicorn 再起動 ==========
echo -e "${GREEN}[4/5] アプリケーション再起動...${NC}"
# systemd サービスがある場合
$SSH_CMD "sudo systemctl restart newfuhi-production 2>/dev/null || \
    (echo 'systemd サービス未設定。Gunicorn を直接再起動します...' && \
     pkill -f gunicorn 2>/dev/null; \
     cd $REMOTE_PATH && source venv/bin/activate && \
     nohup gunicorn project.wsgi:application --bind 127.0.0.1:8000 --workers 2 --daemon)"
echo -e "${GREEN}  再起動完了${NC}"
echo ""

# ========== Step 5: ヘルスチェック ==========
echo -e "${GREEN}[5/5] ヘルスチェック...${NC}"
sleep 3
HTTP_CODE=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/booking/" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}  HTTP $HTTP_CODE - 正常${NC}"
else
    echo -e "${RED}  HTTP $HTTP_CODE - 問題あり。ログを確認してください:${NC}"
    echo -e "  $SSH_CMD \"tail -20 $REMOTE_PATH/debug.log\""
fi

echo ""
echo "========================================"
echo -e "${GREEN}  デプロイ完了!${NC}"
echo "  EC2: $EC2_USER@$EC2_HOST"
echo "  パス: $REMOTE_PATH"
echo "  URL: http://$EC2_HOST"
echo "========================================"
echo ""
