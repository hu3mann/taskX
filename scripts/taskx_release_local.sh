#!/usr/bin/env bash
# TaskX Local Release Script
# Prepares for release by verifying clean state, running tests, and building artifacts.
# Does NOT automatically tag or push - operator controls those steps.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $*"
}

# Detect script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_info "TaskX Local Release Preparation"
log_info "Repo root: $REPO_ROOT"
echo ""

cd "$REPO_ROOT"

# Step 1: Verify git clean
log_step "1/5 Verifying git repository is clean..."
if ! git diff-index --quiet HEAD --; then
    log_error "Git working tree is not clean. Please commit or stash changes first."
    echo ""
    git status --short
    exit 1
fi
log_info "✅ Git working tree is clean"
echo ""

# Step 2: Get current version
log_step "2/5 Reading current version..."
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | head -n 1 | sed 's/version = "\(.*\)"/\1/')
log_info "Current version: $CURRENT_VERSION"
echo ""

# Step 3: Run tests
log_step "3/5 Running unit tests..."
if ! python -m pytest -q; then
    log_error "Tests failed. Fix issues before releasing."
    exit 1
fi
log_info "✅ All tests passed"
echo ""

# Step 4: Build distribution
log_step "4/5 Building distribution packages..."
if ! bash scripts/taskx_build.sh; then
    log_error "Build failed. Check build output above."
    exit 1
fi
log_info "✅ Build completed"
echo ""

# Step 5: Verify clean venv installation
log_step "5/5 Verifying wheel installation in clean environment..."
if ! bash scripts/taskx_verify_clean_venv.sh; then
    log_error "Clean venv verification failed. Build may be broken."
    exit 1
fi
log_info "✅ Clean venv verification passed"
echo ""

# Success banner
echo "═══════════════════════════════════════════════════════════"
log_info "🎉 Release preparation completed successfully!"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Print next steps
echo -e "${BLUE}NEXT STEPS (operator-controlled):${NC}"
echo ""
echo "1. Tag the release:"
echo -e "   ${YELLOW}git tag v${CURRENT_VERSION}${NC}"
echo ""
echo "2. Push the tag to trigger GitHub release workflow:"
echo -e "   ${YELLOW}git push origin v${CURRENT_VERSION}${NC}"
echo ""
echo "3. Monitor the release workflow:"
echo "   https://github.com/OWNER/REPO/actions"
echo ""
echo "4. Once published, verify the release:"
echo "   https://github.com/OWNER/REPO/releases/tag/v${CURRENT_VERSION}"
echo ""
echo -e "${YELLOW}NOTE:${NC} Replace OWNER/REPO with your actual repository path."
echo ""

# Show built artifacts
log_info "Built artifacts:"
ls -lh dist/
echo ""

log_info "Ready to release v${CURRENT_VERSION}"
