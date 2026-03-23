# E2E Tests

Production E2E tests for https://timebaibai.com using headless Chromium (gstack browse).

## Test Suites

| File | Tests | Description |
|------|-------|-------------|
| `test_main.py` | 25 | 4 roles login, workflows, cross-role, permissions, public pages |
| `test_i18n_nav.py` | 21 | i18n navigation, language switching, zh-hant support |
| `test_comprehensive.py` | 131 | All pages, API smoke, mobile responsive, CSRF, edge cases |

**Total: 177 tests**

## Running

These tests require `gstack browse` (headless Chromium CLI) and run against the live production site.

```bash
# Setup
B=~/.claude/skills/gstack/browse/dist/browse

# Run individual suites
python tests/e2e/test_main.py
python tests/e2e/test_i18n_nav.py
python tests/e2e/test_comprehensive.py
```

## Demo Accounts

| Username | Role |
|----------|------|
| demo_owner | Owner (superuser) |
| demo_manager | Manager |
| demo_staff | Staff |
| demo_fortune | Cast |

Password: `demo1234`

## Last Run

2026-03-23: **177/177 PASS**
