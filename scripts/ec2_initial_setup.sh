#!/bin/bash
# ec2_initial_setup.sh
# EC2 上で最初に1回だけ実行する初期セットアップスクリプト
#
# 使い方（ローカルからEC2にコピーして実行）:
#   scp -i newfuhi-key.pem scripts/ec2_initial_setup.sh ubuntu@52.198.72.13:~/
#   ssh -i newfuhi-key.pem ubuntu@52.198.72.13 "bash ~/ec2_initial_setup.sh"

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEPLOY_PATH="/home/ubuntu/NewFUHI"
REPO_URL="https://github.com/FUHI12342/NewFUHI.git"

echo "========================================"
echo "  EC2 Initial Setup for NewFUHI"
echo "========================================"

# 1. システムパッケージ
echo -e "${GREEN}[1/6] システムパッケージのインストール...${NC}"
sudo apt update -qq
sudo apt install -y python3-venv python3-pip python3-dev nginx git redis-server \
    libffi-dev libssl-dev libjpeg-dev zlib1g-dev

# 2. リポジトリクローン
echo -e "${GREEN}[2/6] リポジトリのクローン...${NC}"
if [ -d "$DEPLOY_PATH/.git" ]; then
    echo "  既にクローン済み。pull します..."
    cd "$DEPLOY_PATH"
    git pull origin main
else
    git clone "$REPO_URL" "$DEPLOY_PATH"
    cd "$DEPLOY_PATH"
fi

# 3. Python venv & 依存関係
echo -e "${GREEN}[3/6] Python 仮想環境 & 依存関係...${NC}"
python3 -m venv "$DEPLOY_PATH/venv"
source "$DEPLOY_PATH/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn dj-database-url

# 4. ディレクトリ準備
echo -e "${GREEN}[4/6] ディレクトリ準備...${NC}"
mkdir -p "$DEPLOY_PATH/staticfiles"
mkdir -p "$DEPLOY_PATH/media"
sudo mkdir -p /var/log/newfuhi
sudo chown ubuntu:ubuntu /var/log/newfuhi

# 5. Django 初期化
echo -e "${GREEN}[5/6] Django の初期化...${NC}"
export DJANGO_SETTINGS_MODULE=project.settings
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 6. Nginx 設定（HTTP のみ、シンプル版）
echo -e "${GREEN}[6/6] Nginx の設定...${NC}"
sudo tee /etc/nginx/sites-available/newfuhi > /dev/null << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias /home/ubuntu/NewFUHI/staticfiles/;
        expires 1y;
        access_log off;
    }

    # Media files
    location /media/ {
        alias /home/ubuntu/NewFUHI/media/;
        expires 30d;
    }

    # IoT API（認証不要パス）
    location /booking/api/iot/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    access_log /var/log/nginx/newfuhi-access.log;
    error_log /var/log/nginx/newfuhi-error.log;
}
NGINX_EOF

sudo ln -sf /etc/nginx/sites-available/newfuhi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Gunicorn をバックグラウンド起動
echo -e "${GREEN}Gunicorn を起動...${NC}"
cd "$DEPLOY_PATH"
source venv/bin/activate
pkill -f "gunicorn project.wsgi" 2>/dev/null || true
nohup venv/bin/gunicorn project.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile /var/log/newfuhi/gunicorn-access.log \
    --error-logfile /var/log/newfuhi/gunicorn-error.log \
    --daemon

echo ""
echo "========================================"
echo -e "${GREEN}  セットアップ完了!${NC}"
echo ""
echo "  URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '52.198.72.13')"
echo ""
echo "  次回以降のデプロイ:"
echo "    ローカルで ./scripts/deploy_to_ec2.sh を実行"
echo ""
echo "  .env.production の編集が必要:"
echo "    nano $DEPLOY_PATH/.env.production"
echo "    → SECRET_KEY, LINE_*, PAYMENT_* 等の CHANGE_ME を置換"
echo "========================================"
