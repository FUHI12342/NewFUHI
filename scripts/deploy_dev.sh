#!/bin/bash
# deploy_dev.sh
# ローカルから EC2 dev環境にデプロイするスクリプト
#
# 使い方:
#   ./scripts/deploy_dev.sh
#
# 前提:
#   - SSH 鍵が newfuhi-key.pem に存在
#   - EC2 の GitHub にアクセス可能

set -e

# ========== 設定 ==========
EC2_HOST="52.198.72.13"
EC2_USER="ubuntu"
SSH_KEY="$(dirname "$0")/../newfuhi-key.pem"
REMOTE_PATH="/home/ubuntu/NewFUHI-dev"
BRANCH="dev"
REPO_URL="https://github.com/FUHI12342/NewFUHI.git"

# 色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# SSH コマンド
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $EC2_USER@$EC2_HOST"

echo ""
echo "========================================"
echo "  NewFUHI EC2 Dev Deploy"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# ========== Step 1: ローカルの変更を push ==========
echo -e "${GREEN}[1/6] ローカルの変更を GitHub に push...${NC}"
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

# ========== Step 2: EC2 で clone or pull ==========
echo -e "${GREEN}[2/6] EC2 で git clone/pull...${NC}"
$SSH_CMD << REMOTE
  set -e
  if [ ! -d $REMOTE_PATH ]; then
    echo "  初回セットアップ: clone..."
    git clone -b $BRANCH $REPO_URL $REMOTE_PATH
    cd $REMOTE_PATH
    python3 -m venv venv
  else
    echo "  既存ディレクトリ: fetch + reset..."
    cd $REMOTE_PATH
    git fetch origin $BRANCH
    git reset --hard origin/$BRANCH
  fi
REMOTE
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 3: 依存関係インストール ==========
echo -e "${GREEN}[3/6] 依存関係インストール...${NC}"
$SSH_CMD "cd $REMOTE_PATH && source venv/bin/activate && pip install -q -r requirements.txt"
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 4: マイグレーション & 静的ファイル ==========
echo -e "${GREEN}[4/6] マイグレーション & collectstatic...${NC}"
$SSH_CMD "cd $REMOTE_PATH && source venv/bin/activate && \
    python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput"
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 5: Nginx設定 & サービス設定（初回のみ） ==========
echo -e "${GREEN}[5/6] サービス設定確認 & 再起動...${NC}"
$SSH_CMD << 'REMOTE'
  set -e
  # ログディレクトリ作成
  sudo mkdir -p /var/log/newfuhi

  # systemd サービスファイルのシンボリックリンク（初回のみ）
  if [ ! -f /etc/systemd/system/newfuhi-dev.service ]; then
    echo "  systemd サービスを設定中..."
    sudo cp /home/ubuntu/NewFUHI-dev/config/systemd/newfuhi-dev.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable newfuhi-dev
  fi

  # Nginx設定（初回のみ）
  if [ ! -f /etc/nginx/sites-available/newfuhi-dev ]; then
    echo "  Nginx設定を配置中..."
    sudo cp /home/ubuntu/NewFUHI-dev/config/nginx/dev.conf /etc/nginx/sites-available/newfuhi-dev
    sudo ln -sf /etc/nginx/sites-available/newfuhi-dev /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
  fi

  # アプリケーション再起動
  sudo systemctl restart newfuhi-dev
REMOTE
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 6: ヘルスチェック ==========
echo -e "${GREEN}[6/6] ヘルスチェック...${NC}"
sleep 3
HTTP_CODE=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/admin/" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}  HTTP $HTTP_CODE - 正常${NC}"
else
    echo -e "${RED}  HTTP $HTTP_CODE - 問題あり。ログを確認:${NC}"
    echo -e "  $SSH_CMD \"tail -20 $REMOTE_PATH/debug.log\""
fi

echo ""
echo "========================================"
echo -e "${GREEN}  Dev デプロイ完了!${NC}"
echo "  EC2: $EC2_USER@$EC2_HOST"
echo "  パス: $REMOTE_PATH"
echo "  URL: http://dev.timebaibai.com/admin/"
echo ""
echo -e "${YELLOW}  注意: DNS設定が必要です${NC}"
echo "  dev.timebaibai.com → A レコード $EC2_HOST"
echo "========================================"
echo ""
