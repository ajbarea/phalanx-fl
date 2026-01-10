#!/usr/bin/env bash
# ===========================================================================
# Dependency Update Helper Script
# ===========================================================================
# This script helps you update dependencies in a controlled way.
#
# Usage:
#   ./update_dependencies.sh              # Update all dependencies
#   ./update_dependencies.sh package-name # Update specific package
#
# Examples:
#   ./update_dependencies.sh              # Full update
#   ./update_dependencies.sh pydantic     # Update just Pydantic
#   ./update_dependencies.sh torch        # Update just PyTorch

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() { echo -e "${BLUE}ℹ ${NC}$1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    log_error "uv is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

log_info "UV version: $(uv --version)"
echo ""

# Backup current lock file
if [ -f "uv.lock" ]; then
    cp uv.lock uv.lock.backup
    log_success "Backed up uv.lock to uv.lock.backup"
fi

# Check if specific package was provided
if [ $# -eq 0 ]; then
    # Update all packages
    log_info "Updating ALL dependencies to latest compatible versions..."
    echo ""

    uv lock --upgrade

    log_success "Lock file updated successfully!"
    echo ""
    log_info "To see what changed, run:"
    echo "  git diff uv.lock"

else
    # Update specific package
    PACKAGE="$1"
    log_info "Updating ${PACKAGE} to latest compatible version..."
    echo ""

    uv lock --upgrade-package "${PACKAGE}"

    log_success "${PACKAGE} updated successfully!"
    echo ""
    log_info "To see what changed, run:"
    echo "  git diff uv.lock"
fi

echo ""
log_warning "Next steps:"
echo "  1. Review changes: git diff uv.lock"
echo "  2. Test changes: ./tests/lint.sh --test"
echo "  3. Sync environment: uv sync"
echo "  4. If tests pass, commit the updated uv.lock"
echo ""
log_info "To restore backup if something breaks:"
echo "  mv uv.lock.backup uv.lock && uv sync"
