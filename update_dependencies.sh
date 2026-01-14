#!/bin/bash
# Update Python dependencies using uv lock.
#
# Upgrades all dependencies to their latest compatible versions.
# Creates a backup of uv.lock before making changes.
#
# Usage:
#   ./update_dependencies.sh
#
# Dependencies: uv

set -euo pipefail

# ============================================================================
# Output
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Log an informational message with blue indicator.
#
# Arguments:
#   $1: Message to log
log_info() { echo -e "${BLUE}ℹ ${NC}$1"; }

# Log a success message with green checkmark.
#
# Arguments:
#   $1: Message to log
log_success() { echo -e "${GREEN}✓${NC} $1"; }

# Log a warning message with yellow indicator.
#
# Arguments:
#   $1: Message to log
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

# Log an error message with red indicator.
#
# Arguments:
#   $1: Message to log
log_error() { echo -e "${RED}✗${NC} $1"; }

# ============================================================================
# Main
# ============================================================================

if ! command -v uv &> /dev/null; then
    log_error "uv is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

log_info "UV version: $(uv --version)"
echo ""

# Preserve ability to restore if update causes issues.
if [ -f "uv.lock" ]; then
    BACKUP_FILE="uv.lock.backup.$(date +%s)"
    cp uv.lock "${BACKUP_FILE}"
    log_success "Backed up uv.lock to ${BACKUP_FILE}"
    
    # Keep only the last 3 backups to prevent accumulation.
    ls -t uv.lock.backup.* 2>/dev/null | tail -n +4 | xargs -r rm -f
fi

log_info "Updating ALL dependencies to latest compatible versions..."
echo ""

uv lock --upgrade

log_success "Lock file updated successfully!"
echo ""
log_info "To see what changed, run:"
echo "  git diff uv.lock"


echo ""
log_warning "Next steps:"
echo "  1. Review changes: git diff uv.lock"
echo "  2. Test changes: make test"
echo "  3. Sync environment: uv sync"
echo "  4. If tests pass, commit the updated uv.lock"
echo ""
log_info "To restore backup if something breaks:"
echo "  # Find available backups:"
echo "  ls -t uv.lock.backup.*"
echo ""
echo "  # Restore latest (safely):"
echo "  [ -f uv.lock.backup.* ] && mv \$(ls -t uv.lock.backup.* | head -n1) uv.lock && uv sync"
