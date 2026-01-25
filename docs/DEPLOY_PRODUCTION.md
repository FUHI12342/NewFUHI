# Production Deployment Guide

This guide covers the complete production deployment process for NewFUHI Django application on AWS EC2.

## Overview

The production deployment follows this workflow:
1. **PR → main** - Code review and merge
2. **main → tag** - Create release tag
3. **EC2 deployment** - Pull, setup, and restart services
4. **Health verification** - Confirm deployment via /healthz endpoint

## Prerequisites

### Server Setup (One-time)

```bash
# 1. Create user and directories
sudo useradd -m -s /bin/bash newfuhi
sudo mkdir -p /var/www/newfuhi
sudo mkdir -p /var/log/newfuhi
sudo chown -R newfuhi:newfuhi /var/www/newfuhi /var/log/newfuhi

# 2. Install system dependencies
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git

# 3. Setup Python virtual environment
sudo -u newfuhi python3 -m venv /var/www/newfuhi/venv
sudo -u newfuhi /var/www/newfuhi/venv/bin/pip install --upgrade pip

# 4. Clone repository
cd /var/www/newfuhi
sudo -u newfuhi git clone https://github.com/your-org/newfuhi.git .

# 5. Install Python dependencies
sudo -u newfuhi /var/www/newfuhi/venv/bin/pip install -r requirements.txt

# 6. Setup configuration files
sudo cp config/systemd/newfuhi-production.service /etc/systemd/system/
sudo cp config/nginx/production.conf /etc/nginx/sites-available/newfuhi-production
sudo ln -s /etc/nginx/sites-available/newfuhi-production /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 7. Create environment file
sudo -u newfuhi cp .env.staging.example /var/www/newfuhi/.env.production
# Edit .env.production with production values

# 8. Setup SSL certificates (replace with your actual certificates)
sudo mkdir -p /etc/ssl/certs /etc/ssl/private
# Copy your SSL certificates to:
# /etc/ssl/certs/newfuhi.crt
# /etc/ssl/private/newfuhi.key

# 9. Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable newfuhi-production
sudo systemctl enable nginx
```

## Deployment Process

### Step 1: Create Release Tag

```bash
# On your local machine
git checkout main
git pull origin main

# Create and push release tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### Step 2: Deploy to EC2

```bash
# SSH to production server
ssh user@your-production-server

# Switch to newfuhi user
sudo -u newfuhi -i

# Navigate to application directory
cd /var/www/newfuhi

# Fetch latest changes
git fetch --all --tags

# Checkout specific tag
git checkout v1.0.0

# Get current git SHA for health check
export CURRENT_SHA=$(git rev-parse HEAD)
echo "Deploying SHA: $CURRENT_SHA"

# Install/update dependencies
/var/www/newfuhi/venv/bin/pip install -r requirements.txt

# Run Django management commands
export DJANGO_SETTINGS_MODULE=project.settings.production
/var/www/newfuhi/venv/bin/python manage.py check
/var/www/newfuhi/venv/bin/python manage.py migrate
/var/www/newfuhi/venv/bin/python manage.py collectstatic --noinput

# Update systemd service with current git SHA
sudo sed -i "s/Environment=APP_GIT_SHA=.*/Environment=APP_GIT_SHA=$CURRENT_SHA/" /etc/systemd/system/newfuhi-production.service

# Reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl restart newfuhi-production
sudo systemctl restart nginx

# Check service status
sudo systemctl status newfuhi-production
sudo systemctl status nginx
```

### Step 3: Verify Deployment

```bash
# Check health endpoint
curl -s https://your-domain.com/healthz | jq .

# Expected response:
{
  "status": "ok",
  "git_sha": "abc123...",
  "django": "4.2.25",
  "settings": "project.settings.production",
  "env": "production"
}

# Verify git SHA matches deployed version
echo "Expected SHA: $CURRENT_SHA"
echo "Deployed SHA: $(curl -s https://your-domain.com/healthz | jq -r .git_sha)"

# Test main application
curl -I https://your-domain.com/
```

## Rollback Procedure

If deployment fails, rollback to previous version:

```bash
# Find previous working tag
git tag -l --sort=-version:refname | head -5

# Checkout previous version
git checkout v1.0.0-previous

# Update git SHA
export ROLLBACK_SHA=$(git rev-parse HEAD)
sudo sed -i "s/Environment=APP_GIT_SHA=.*/Environment=APP_GIT_SHA=$ROLLBACK_SHA/" /etc/systemd/system/newfuhi-production.service

# Restart services
sudo systemctl daemon-reload
sudo systemctl restart newfuhi-production

# Verify rollback
curl -s https://your-domain.com/healthz | jq .
```

## Database Policy

**Important**: `db.sqlite3` is NOT deployed to production.

- **Local development**: Uses SQLite (`db.sqlite3`)
- **Production**: Uses RDS PostgreSQL/MySQL via `DATABASE_URL`
- **Migration**: Database schema is migrated via `manage.py migrate`
- **Data**: Production data stays in RDS, never in SQLite

The `.gitignore` includes `db.sqlite3` to prevent accidental commits of local database files.

## Monitoring

### Log Files

```bash
# Application logs
sudo journalctl -u newfuhi-production -f

# Nginx logs
sudo tail -f /var/log/nginx/newfuhi-production-access.log
sudo tail -f /var/log/nginx/newfuhi-production-error.log

# Gunicorn logs
sudo tail -f /var/log/newfuhi/gunicorn-access.log
sudo tail -f /var/log/newfuhi/gunicorn-error.log
```

### Health Monitoring

Set up automated health checks:

```bash
# Add to crontab for monitoring
*/5 * * * * curl -f https://your-domain.com/healthz > /dev/null 2>&1 || echo "Health check failed" | mail -s "NewFUHI Health Alert" admin@your-domain.com
```

## Security Notes

1. **SSL/TLS**: Always use HTTPS in production
2. **Firewall**: Configure UFW to allow only necessary ports (80, 443, 22)
3. **Updates**: Regularly update system packages
4. **Secrets**: Never commit secrets to git, use environment variables
5. **Backups**: Regular database and media file backups

## Troubleshooting

### Common Issues

1. **Service won't start**: Check `sudo journalctl -u newfuhi-production`
2. **502 Bad Gateway**: Verify Gunicorn is running on port 8000
3. **Static files not loading**: Run `collectstatic` and check Nginx config
4. **Database errors**: Verify `DATABASE_URL` in `.env.production`

### Emergency Contacts

- **DevOps**: devops@your-domain.com
- **On-call**: +1-xxx-xxx-xxxx
- **Status Page**: https://status.your-domain.com