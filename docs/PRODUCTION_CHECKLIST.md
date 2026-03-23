# Production Launch Checklist — timebaibai.com

最終確認日: 2026-03-23

---

## Security

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | DEBUG=False | PASS | .env + systemd ENV=production |
| 2 | SECRET_KEY | PASS | env_required() で起動時検証 |
| 3 | ALLOWED_HOSTS | PASS | 環境変数で設定 |
| 4 | CSRF_TRUSTED_ORIGINS | PASS | HTTPS自動生成 |
| 5 | SESSION_COOKIE_SECURE | PASS | DEBUG=False時に自動有効 |
| 6 | CSRF_COOKIE_SECURE | PASS | 同上 |
| 7 | SESSION_COOKIE_HTTPONLY | PASS | 常時有効 |
| 8 | CSRF_COOKIE_HTTPONLY | PASS | 常時有効 |
| 9 | SECURE_SSL_REDIRECT | PASS | DEBUG=False時に自動有効 |
| 10 | SECURE_PROXY_SSL_HEADER | PASS | X-Forwarded-Proto対応 |
| 11 | X_FRAME_OPTIONS=DENY | PASS | |
| 12 | HSTS (Nginx) | PASS | max-age=31536000; includeSubDomains |
| 13 | CSP (Nginx) | PASS | default-src 'self', unsafe-eval (Alpine.js) |
| 14 | XSS sanitization (bleach) | PASS | Notice, SiteSettings, Store, HomepageCustomBlock |
| 15 | CHECKIN_QR_SECRET | PASS | 専用シークレット、SECRET_KEYフォールバックなし |
| 16 | IP validation | PASS | X-Forwarded-For バリデーション |
| 17 | Rate limiting | PASS | フィードバックAPI 10/hour, チャット 20/5min |
| 18 | Content-Type checks | PASS | 全CSRF exemptエンドポイント |
| 19 | 敏感ファイルブロック | PASS | Nginx: .log/.pem/.env/.sqlite3/.pyc |
| 20 | Django check --deploy | PASS | 0 issues (1 silenced: W004 HSTS) |

## SSL

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | 証明書有効 | PASS | 〜2026-04-26 (残33日) |
| 2 | 自動更新 | PASS | certbot.timer 1日2回 |
| 3 | HTTP→HTTPS リダイレクト | PASS | Nginx 301 |

## Services

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | newfuhi (gunicorn) | PASS | active, workers=2 |
| 2 | newfuhi-celery | PASS | active |
| 3 | newfuhi-celerybeat | PASS | active |
| 4 | nginx | PASS | active |
| 5 | redis | PASS | active |
| 6 | Restart=always | PASS | systemd自動再起動設定 |

## Backup

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | 日次DBバックアップ | PASS | cron 02:00 (S3), 18:00 (ローカル) |
| 2 | メディアS3同期 | PASS | cron 03:00 |
| 3 | デプロイ前バックアップ | PASS | deploy_to_ec2.sh 自動実行 |
| 4 | バックアップ保持ポリシー | PASS | 直近3件保持、古いものは自動削除 |

## Dependencies

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | Django | PASS | 4.2.29 (LTS, 全CVE修正済み) |
| 2 | cryptography | PASS | 46.0.5 |
| 3 | Pillow | PASS | 12.1.1 |
| 4 | PyJWT | PASS | 2.12.1 |
| 5 | pip-audit 残件 | INFO | social-auth-app-django 5.4.3 (5.6+はDjango 5.1+要求) |

## Monitoring

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | ヘルスチェック | PASS | /healthz エンドポイント |
| 2 | ログローテーション | PASS | /etc/logrotate.d/newfuhi (14日保持) |
| 3 | Sentry | READY | SDK設定済み。SENTRY_DSN を .env に追加で有効化 |

## Pages (E2E verified: 177/177 PASS)

| # | 項目 | 状態 |
|---|------|------|
| 1 | 公開ページ (11) | PASS |
| 2 | 管理ページ (30) | PASS |
| 3 | 4ロールログイン | PASS |
| 4 | i18n (zh-hant/en) | PASS |
| 5 | 404ページ | PASS (カスタム) |
| 6 | モバイルレスポンシブ | PASS |

## Infrastructure

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | ディスク空き | PASS | 79% (1.5GB空き) |
| 2 | メモリ | INFO | 911MB (702MB使用) — 監視推奨 |
| 3 | DB | INFO | SQLite 34MB, ~90,000行。現規模で問題なし |

---

## 今後の対応 (ローンチ後)

| 項目 | 優先度 | 説明 |
|---|---|---|
| Sentry有効化 | 高 | sentry.io でプロジェクト作成 → DSN取得 → .env追加 |
| メモリ監視 | 高 | 911MBは限界的。負荷増加時にインスタンス拡張検討 |
| Django 5.x 移行 | 中 | Django 4.2 LTS は2026-04サポート終了。5.x移行計画 |
| PostgreSQL 移行 | 低 | 同時書き込み負荷増加時に検討 |
| CSP nonce化 | 低 | unsafe-inline/unsafe-eval の段階的排除 |
