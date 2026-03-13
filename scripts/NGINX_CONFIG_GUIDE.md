# Nginx Configuration Guide for IoT API Basic Auth Bypass

## Objective

Exclude the `/booking/api/iot/*` endpoints from Basic authentication while keeping Basic auth enabled for all other paths on `timebaibai.com`.

## Prerequisites

- SSH access to timebaibai.com server
- Sudo privileges
- Backup created (via `backup_server.sh`)

## Step-by-Step Instructions

### 1. SSH into Server

```bash
ssh -i newfuhi-key.pem ubuntu@<server-ip>
```

### 2. Create Backup (if not done)

```bash
cd /path/to/deployment
sudo ./scripts/backup_server.sh
```

Verify backup created:
```bash
ls -lh /var/backups/ | grep timebaibai
```

### 3. Identify Nginx Configuration File

Find which config file handles `timebaibai.com`:

```bash
sudo nginx -T | grep -B 5 "server_name.*timebaibai.com" | head -n 20
```

Common locations:
- `/etc/nginx/sites-available/timebaibai` (or timebaibai.conf)
- `/etc/nginx/conf.d/timebaibai.conf`
- `/etc/nginx/sites-enabled/timebaibai` (symlink to sites-available)

### 4. Edit Configuration File

Open the identified file with sudo:

```bash
sudo nano /etc/nginx/sites-available/timebaibai
# or
sudo vim /etc/nginx/sites-available/timebaibai
```

### 5. Locate the `server` Block for timebaibai.com

Find the server block that contains:
```nginx
server {
    server_name timebaibai.com www.timebaibai.com;
    ...
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    ...
}
```

### 6. Add IoT API Location Block

**IMPORTANT**: Add this BEFORE any other location blocks (or at least before the root `/` location).

The `^~` prefix gives this location priority over regex matches.

```nginx
server {
    server_name timebaibai.com www.timebaibai.com;
    
    # ... SSL and other settings ...
    
    # IoT API - Bypass Basic authentication
    location ^~ /booking/api/iot/ {
        auth_basic off;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Proxy to Django backend (adjust port if different)
        proxy_pass http://127.0.0.1:8000;
    }
    
    # Other locations remain unchanged
    location / {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_pass http://127.0.0.1:8000;
    }
}
```

**Note**: Adjust `proxy_pass` URL if your Django backend listens on a different address/port. Check existing location blocks to match the upstream configuration.

### 7. Test Configuration

**CRITICAL**: Always test before reloading!

```bash
sudo nginx -t
```

Expected output:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

If errors appear:
- Read the error message carefully (shows line number and issue)
- Common issues:
  - Missing semicolon (`;`)
  - Mismatched braces (`{` `}`)
  - Typo in directive name
  - Wrong indentation (not fatal but confusing)

### 8. Reload Nginx

Only after successful `nginx -t`:

```bash
sudo systemctl reload nginx
```

Verify reload succeeded:
```bash
sudo systemctl status nginx
```

Look for:
```
Active: active (running)
```

### 9. Verify Configuration Changes

#### Test A: IoT API - No Basic Auth

From your Mac or another client:

```bash
curl -i \
  -H "X-API-KEY: <your-actual-api-key>" \
  "https://timebaibai.com/booking/api/iot/config/?device=pico2w_001" \
  | head -n 40
```

**Expected**:
- ✓ NO `WWW-Authenticate: Basic` header in response
- ✓ Status: 200 (success) or 403 (API key invalid) or 404 (endpoint not configured)
- ✗ Status: 401 = FAIL (Basic auth still active)

#### Test B: Other Paths - Basic Auth Still Active

```bash
curl -i "https://timebaibai.com/" | head -n 20
```

**Expected**:
- ✓ `HTTP/1.1 401 Unauthorized`
- ✓ `WWW-Authenticate: Basic realm="Restricted"`

Test with credentials:
```bash
curl -i -u "username:password" "https://timebaibai.com/" | head -n 20
```

**Expected**:
- ✓ `HTTP/1.1 200 OK` (or appropriate status)
- ✓ Page content returned

### 10. Monitor Logs (Optional)

Watch for any errors after reload:

```bash
sudo tail -f /var/log/nginx/error.log
```

Press `Ctrl+C` to stop.

Check access logs to see IoT API requests coming through:

```bash
sudo tail -f /var/log/nginx/access.log | grep "/booking/api/iot/"
```

## Rollback Procedure

If something goes wrong:

```bash
cd /path/to/deployment
sudo ./scripts/rollback_server.sh
```

Select the most recent backup timestamp and follow prompts.

The rollback script will:
1. Restore `/etc/nginx/` from backup
2. Test configuration (`nginx -t`)
3. Ask for confirmation before reloading

## Verification Checklist

- [ ] Backup created in `/var/backups/timebaibai_<timestamp>/`
- [ ] Configuration file edited with `location ^~ /booking/api/iot/` block
- [ ] `sudo nginx -t` shows "syntax is ok"
- [ ] `sudo systemctl reload nginx` successful
- [ ] `sudo systemctl status nginx` shows "active (running)"
- [ ] IoT API test (curl) shows NO `WWW-Authenticate` header
- [ ] Root path test (curl) shows `401` with `WWW-Authenticate` header
- [ ] No errors in `/var/log/nginx/error.log`

## Security Note

After this change:
- `/booking/api/iot/*` endpoints are **publicly accessible** (no Basic auth)
- **Django API key validation** is the primary security mechanism
- Ensure Django's `IoTAPIView` or equivalent validates the `X-API-KEY` header
- Consider additional rate limiting or IP whitelisting if needed

Example Django middleware/view check:
```python
api_key = request.headers.get('X-API-KEY')
if api_key != settings.IOT_API_KEY:
    return JsonResponse({'error': 'Unauthorized'}, status=403)
```

## Common Issues

### Issue: "nginx: [emerg] duplicate location"
**Cause**: Another location block already matches `/booking/api/iot/`

**Fix**: Check for existing blocks. Use `^~` prefix to ensure priority, or remove conflicting block.

### Issue: Still getting 401 on IoT API
**Cause 1**: Location block not matched (wrong path or precedence)

**Fix**: Verify exact path in curl matches location. Try adding `^~` prefix for priority.

**Cause 2**: Reload didn't actually reload config

**Fix**: Try `sudo systemctl restart nginx` (full restart instead of reload).

### Issue: Entire site now bypasses Basic auth
**Cause**: IoT location block too broad or catchall

**Fix**: Ensure location is `^~ /booking/api/iot/` (specific path). Check that other `location /` blocks still have `auth_basic` directives.

### Issue: Django returns 404 for IoT endpoints
**Cause**: Django URL routing doesn't have `/booking/api/iot/` configured

**Fix**: This is a Django application issue, not Nginx. Check Django's `urls.py` and ensure IoT API views are registered.

## Complete Example Configuration

Here's a complete annotated example:

```nginx
server {
    listen 443 ssl http2;
    server_name timebaibai.com www.timebaibai.com;
    
    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/timebaibai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/timebaibai.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # IoT API - NO Basic Auth (highest priority)
    location ^~ /booking/api/iot/ {
        auth_basic off;  # Explicitly disable Basic auth
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_pass http://127.0.0.1:8000;
    }
    
    # All other paths - Basic Auth required
    location / {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_pass http://127.0.0.1:8000;
    }
    
    # Static files (if served by Nginx)
    location /static/ {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
        alias /var/www/timebaibai/static/;
    }
    
    # Media files (if served by Nginx)
    location /media/ {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
        alias /var/www/timebaibai/media/;
    }
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name timebaibai.com www.timebaibai.com;
    return 301 https://$server_name$request_uri;
}
```

## Summary

1. Backup  server configuration
2. Edit Nginx config to add `location ^~ /booking/api/iot/` with `auth_basic off;`
3. Test with `nginx -t`
4. Reload with `systemctl reload nginx`
5. Verify with curl: IoT API no auth, other paths require auth
6. Monitor logs for issues

The IoT API is now accessible without Basic authentication, relying on Django's API key validation for security.
