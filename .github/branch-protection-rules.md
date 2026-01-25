# Branch Protection Rules Configuration

This document describes the recommended branch protection rules for the NewFUHI repository.

## Protected Branches

### Main/Master Branch
- **Branch name**: `main` or `master`
- **Protection level**: Maximum
- **Required settings**:
  - ✅ Require pull request reviews before merging
  - ✅ Require review from code owners (if CODEOWNERS file exists)
  - ✅ Dismiss stale PR approvals when new commits are pushed
  - ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - ✅ Require conversation resolution before merging
  - ✅ Restrict pushes that create files larger than 100MB
  - ✅ Include administrators in restrictions

### Develop Branch
- **Branch name**: `develop`
- **Protection level**: Medium
- **Required settings**:
  - ✅ Require pull request reviews before merging
  - ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - ⚠️ Allow administrators to bypass restrictions

### Staging Branch
- **Branch name**: `staging`
- **Protection level**: Medium
- **Required settings**:
  - ✅ Require pull request reviews before merging
  - ✅ Require status checks to pass before merging
  - ⚠️ Allow administrators to bypass restrictions

## Required Status Checks

The following GitHub Actions workflows must pass before merging:

### For all protected branches:
- `PR Validation / validate` - Runs linting, type checking, and tests
- `Django Check` - Ensures Django system check passes

### Additional checks for main/master:
- `Security Scan` - Runs security vulnerability checks
- `Production Readiness` - Validates production deployment readiness

## Setup Instructions

### 1. Configure Branch Protection via GitHub UI

1. Go to repository **Settings** → **Branches**
2. Click **Add rule** for each protected branch
3. Configure settings as specified above

### 2. Configure Branch Protection via GitHub CLI

```bash
# Main branch protection
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["PR Validation / validate"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null

# Develop branch protection
gh api repos/:owner/:repo/branches/develop/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["PR Validation / validate"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

### 3. Configure Branch Protection via Terraform

```hcl
resource "github_branch_protection" "main" {
  repository_id = github_repository.newfuhi.node_id
  pattern       = "main"

  required_status_checks {
    strict = true
    contexts = [
      "PR Validation / validate",
      "Django Check"
    ]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews          = true
    require_code_owner_reviews     = true
  }

  enforce_admins = true
}

resource "github_branch_protection" "develop" {
  repository_id = github_repository.newfuhi.node_id
  pattern       = "develop"

  required_status_checks {
    strict = true
    contexts = [
      "PR Validation / validate"
    ]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
  }

  enforce_admins = false
}
```

## File Size Restrictions

### Git LFS Configuration
For files larger than 100MB, use Git LFS:

```bash
# Track large files with Git LFS
git lfs track "*.zip"
git lfs track "*.tar.gz"
git lfs track "*.db"
git lfs track "media/**"

# Add .gitattributes
git add .gitattributes
git commit -m "Configure Git LFS for large files"
```

### .gitignore Additions
```gitignore
# Large files that should not be committed
*.zip
*.tar.gz
*.rar
*.7z
*.bak
*.backup
*.old
*.tmp

# Database files
*.db
*.sqlite
*.sqlite3

# Log files
*.log
logs/

# OS generated files
.DS_Store
Thumbs.db
```

## Enforcement

### Local Git Hooks
- Pre-commit hook validates file sizes and types
- Pre-push hook prevents direct pushes to protected branches

### GitHub Actions
- PR validation workflow runs on all pull requests
- Deployment workflows respect branch protection rules

### Manual Override
In emergency situations, administrators can bypass restrictions:
```bash
# Bypass pre-commit hook (local)
git commit --no-verify

# Bypass pre-push hook (local)
git push --no-verify

# Force push (DANGEROUS - requires admin privileges)
git push --force-with-lease
```

## Monitoring and Alerts

### GitHub Notifications
- Enable notifications for:
  - Failed status checks
  - Force pushes to protected branches
  - Branch protection rule changes

### Slack/Discord Integration
Configure webhooks to notify team channels of:
- Pull request reviews
- Failed deployments
- Security alerts

## Troubleshooting

### Common Issues

1. **Status check not found**
   - Ensure GitHub Actions workflow names match exactly
   - Check workflow file syntax and triggers

2. **Cannot push to protected branch**
   - Create a feature branch and submit a pull request
   - Ensure all required status checks pass

3. **Large file rejected**
   - Use Git LFS for files >100MB
   - Consider external storage for very large assets

4. **Pre-commit hook fails**
   - Review file sizes and types
   - Fix validation issues or use `--no-verify` if necessary

### Getting Help

- Check GitHub repository settings
- Review GitHub Actions workflow logs
- Contact repository administrators
- Refer to GitHub documentation on branch protection