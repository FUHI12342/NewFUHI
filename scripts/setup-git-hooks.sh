#!/bin/bash
# Setup Git hooks for NewFUHI project

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_DIR="$REPO_ROOT/.githooks"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "🔧 Setting up Git hooks for NewFUHI project..."

# Create .git/hooks directory if it doesn't exist
mkdir -p "$GIT_HOOKS_DIR"

# Install pre-commit hook
if [ -f "$HOOKS_DIR/pre-commit" ]; then
    echo "Installing pre-commit hook..."
    cp "$HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo "✅ Pre-commit hook installed"
else
    echo "⚠️  Pre-commit hook not found in $HOOKS_DIR"
fi

# Install pre-push hook
if [ -f "$HOOKS_DIR/pre-push" ]; then
    echo "Installing pre-push hook..."
    cp "$HOOKS_DIR/pre-push" "$GIT_HOOKS_DIR/pre-push"
    chmod +x "$GIT_HOOKS_DIR/pre-push"
    echo "✅ Pre-push hook installed"
else
    echo "⚠️  Pre-push hook not found in $HOOKS_DIR"
fi

# Set up Git configuration for hooks
echo "Configuring Git hooks path..."
git config core.hooksPath "$HOOKS_DIR"

echo ""
echo "🎉 Git hooks setup completed!"
echo ""
echo "Installed hooks:"
echo "- pre-commit: Validates file sizes and types"
echo "- pre-push: Prevents direct pushes to protected branches"
echo ""
echo "To test the hooks:"
echo "1. Try committing a large file (>100MB)"
echo "2. Try pushing directly to main/master branch"
echo ""
echo "To bypass hooks (NOT RECOMMENDED):"
echo "- git commit --no-verify"
echo "- git push --no-verify"
echo ""