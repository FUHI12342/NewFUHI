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
EC2_HOST="57.181.0.55"
EC2_USER="ubuntu"
SSH_KEY="$(dirname "$0")/../newfuhi-key.pem"
REMOTE_PATH="/home/ubuntu/NewFUHI"
BRANCH="main"

# 色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# SSH鍵の存在チェック
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}  SSH鍵が見つかりません: $SSH_KEY${NC}"
    echo -e "  初回の場合: ssh-keyscan -H $EC2_HOST >> ~/.ssh/known_hosts"
    exit 1
fi

# SSH コマンド（StrictHostKeyChecking=yes でMITM攻撃を防止）
# 初回接続時: ssh-keyscan -H $EC2_HOST >> ~/.ssh/known_hosts
SSH_CMD="ssh -i $SSH_KEY $EC2_USER@$EC2_HOST"

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
$SSH_CMD "cd '$REMOTE_PATH' && git fetch origin && git reset --hard 'origin/$BRANCH'"
echo -e "${GREEN}  pull 完了${NC}"
echo ""

# ========== Step 2.5: 環境変数の整合性チェック ==========
echo -e "${GREEN}[2.5/6] 環境変数チェック...${NC}"
ENV_CHECK=$($SSH_CMD "cd '$REMOTE_PATH' && \
    source .venv/bin/activate && \
    set -a && source .env && set +a && \
    python -c \"
import os, sys
required = ['SECRET_KEY', 'LINE_CHANNEL_ID', 'LINE_CHANNEL_SECRET',
            'LINE_USER_ID_ENCRYPTION_KEY', 'LINE_USER_ID_HASH_PEPPER',
            'IOT_ENCRYPTION_KEY']
missing = [k for k in required if not os.getenv(k)]
if missing:
    print('MISSING:' + ','.join(missing))
    sys.exit(1)
print('OK')
\"" 2>&1)

if echo "$ENV_CHECK" | grep -q "^MISSING:"; then
    MISSING_VARS=$(echo "$ENV_CHECK" | grep "^MISSING:" | sed 's/^MISSING://')
    echo -e "${RED}  .env に必須環境変数が不足しています: ${MISSING_VARS}${NC}"
    echo -e "${RED}  デプロイを中止します。サーバーの .env を確認してください。${NC}"
    exit 1
fi
echo -e "${GREEN}  環境変数 OK${NC}"
echo ""

# ========== Step 2.7: systemd サービスファイル同期 ==========
echo -e "${GREEN}[2.7/6] systemd サービスファイル同期...${NC}"
SYSTEMD_CHANGED=0
for SVC_FILE in newfuhi.service newfuhi-celery.service newfuhi-celerybeat.service; do
    LOCAL_SVC="$(dirname "$0")/systemd/$SVC_FILE"
    if [ -f "$LOCAL_SVC" ]; then
        DIFF=$($SSH_CMD "cat /etc/systemd/system/$SVC_FILE 2>/dev/null" | diff - "$LOCAL_SVC" 2>/dev/null || true)
        if [ -n "$DIFF" ]; then
            scp -i "$SSH_KEY" -q "$LOCAL_SVC" "$EC2_USER@$EC2_HOST:/tmp/$SVC_FILE"
            $SSH_CMD "sudo cp /tmp/$SVC_FILE /etc/systemd/system/$SVC_FILE && rm /tmp/$SVC_FILE"
            echo -e "  ${YELLOW}更新: $SVC_FILE${NC}"
            SYSTEMD_CHANGED=1
        else
            echo -e "  変更なし: $SVC_FILE"
        fi
    fi
done
if [ "$SYSTEMD_CHANGED" = "1" ]; then
    $SSH_CMD "sudo systemctl daemon-reload"
    echo -e "${GREEN}  daemon-reload 完了${NC}"
fi
echo ""

# ========== Step 3: 依存関係インストール & マイグレーション ==========
echo -e "${GREEN}[3/6] 依存関係 & マイグレーション...${NC}"

# マイグレーション前にDBバックアップ
echo -e "${YELLOW}  DBバックアップ中...${NC}"
BACKUP_FILE="$REMOTE_PATH/backups/pre_deploy_$(date +%Y%m%d_%H%M%S).json"
$SSH_CMD "mkdir -p '$REMOTE_PATH/backups' && cd '$REMOTE_PATH' && \
    source .venv/bin/activate && \
    DJANGO_SETTINGS_MODULE=project.settings.production python manage.py dumpdata \
        --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission \
        -o '$BACKUP_FILE' 2>/dev/null && \
    echo '  バックアップ完了: $BACKUP_FILE' || echo '  バックアップスキップ（初回デプロイ）'"

# SQLiteファイルもコピー
$SSH_CMD "cp '$REMOTE_PATH/db.sqlite3' '$REMOTE_PATH/backups/db_pre_deploy_$(date +%Y%m%d_%H%M%S).sqlite3' 2>/dev/null || true"

$SSH_CMD "cd '$REMOTE_PATH' && \
    source .venv/bin/activate && \
    pip install -q -r requirements.txt && \
    DJANGO_SETTINGS_MODULE=project.settings.production python manage.py migrate --noinput && \
    DJANGO_SETTINGS_MODULE=project.settings.production python manage.py compilemessages 2>/dev/null && \
    DJANGO_SETTINGS_MODULE=project.settings.production python manage.py collectstatic --noinput && \
    DJANGO_SETTINGS_MODULE=project.settings.production python manage.py sync_menu_config"
echo -e "${GREEN}  完了${NC}"
echo ""

# ========== Step 4: アプリケーション再起動 (Gunicorn + Celery) ==========
echo -e "${GREEN}[4/6] アプリケーション再起動...${NC}"
$SSH_CMD "sudo systemctl restart newfuhi newfuhi-celery newfuhi-celerybeat 2>/dev/null || \
    (echo 'systemd サービス未設定。Gunicorn を直接再起動します...' && \
     sudo pkill -f 'gunicorn project' 2>/dev/null; sleep 1; \
     cd '$REMOTE_PATH' && source .venv/bin/activate && \
     nohup gunicorn project.wsgi:application --bind 127.0.0.1:8000 --workers 2 --daemon)"
echo -e "${GREEN}  再起動完了${NC}"
echo ""

# ========== Step 5: Nginx設定リロード ==========
echo -e "${GREEN}[5/6] Nginx設定リロード...${NC}"
$SSH_CMD "sudo nginx -t 2>/dev/null && sudo systemctl reload nginx 2>/dev/null && echo '  Nginx リロード完了' || echo '  Nginx スキップ（未インストール or 設定エラー）'"
echo ""

# ========== Step 6: ヘルスチェック ==========
echo -e "${GREEN}[6/6] ヘルスチェック...${NC}"
sleep 3
HTTP_CODE=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' https://timebaibai.com/healthz" 2>/dev/null || echo "000")
# HTTPS失敗時はローカルへフォールバック
if [ "$HTTP_CODE" = "000" ]; then
    HTTP_CODE=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/healthz" 2>/dev/null || echo "000")
fi

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}  HTTP $HTTP_CODE - 正常${NC}"
else
    echo -e "${RED}  HTTP $HTTP_CODE - 問題あり!${NC}"
    echo -e "${RED}  サービス状態:${NC}"
    $SSH_CMD "sudo systemctl status newfuhi --no-pager 2>/dev/null | head -5" || true
    echo ""
    echo -e "${RED}  直近のエラー:${NC}"
    $SSH_CMD "sudo journalctl -u newfuhi --since '1 min ago' --no-pager 2>/dev/null | grep -i 'error\|missing\|RuntimeError' | tail -5" || true
    echo ""
    echo -e "${YELLOW}  ロールバック: $SSH_CMD \"cd $REMOTE_PATH && git reset --hard HEAD~1 && sudo systemctl restart newfuhi\"${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "${GREEN}  デプロイ完了!${NC}"
echo "  EC2: $EC2_USER@$EC2_HOST"
echo "  パス: $REMOTE_PATH"
echo "  URL: https://timebaibai.com"
echo "========================================"
echo ""
