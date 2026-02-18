#!/usr/bin/env bash
# TaskX Unified Installer and Upgrader
# Installs or upgrades TaskX in a repository.
# Can be run via: curl -fsSL https://raw.githubusercontent.com/hu3mann/taskX/main/scripts/install.sh | bash

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default Configuration
DEFAULT_REPO_URL="https://github.com/hu3mann/taskX.git"
DEFAULT_REF="main"
FORCE_REINSTALL=false
TARGET_VERSION=""
USE_LATEST=false

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --version <v>   Install specific version/tag/branch"
    echo "  --latest        Install latest version from git remote"
    echo "  --force         Force re-installation"
    echo "  --help          Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --version)
            TARGET_VERSION="$2"
            shift
            shift
            ;;
        --latest)
            USE_LATEST=true
            shift
            ;;
        --force)
            FORCE_REINSTALL=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Find repository root by walking up to find .git or pyproject.toml
find_repo_root() {
    local dir="$PWD"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.git" ] || [ -f "$dir/pyproject.toml" ]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    # Fallback: if we are in a directory that looks like a project but no git/pyproject, just use CWD
    # But warn the user.
    log_warn "Could not find repository root (.git or pyproject.toml). Using current directory."
    echo "$PWD"
    return 0
}

# Parse .taskx-pin file into global variables
parse_pin_file() {
    local pin_file="$1"

    if [ ! -f "$pin_file" ]; then
        return 1
    fi

    # Read pin file
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # Trim whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)

        case "$key" in
            install) PIN_INSTALL_METHOD="$value" ;;
            repo) PIN_REPO_URL="$value" ;;
            ref) PIN_REF="$value" ;;
            path) PIN_WHEEL_PATH="$value" ;;
        esac
    done < "$pin_file"
    return 0
}

write_pin_file() {
    local pin_file="$1"
    local method="$2"
    local repo="$3"
    local ref="$4"
    local path="$5"

    log_info "Updating $pin_file..."

    if [ "$method" = "git" ]; then
        cat > "$pin_file" <<EOF
install=git
repo=$repo
ref=$ref
EOF
    elif [ "$method" = "wheel" ]; then
        cat > "$pin_file" <<EOF
install=wheel
path=$path
EOF
    fi
}

main() {
    log_info "TaskX Installer/Upgrader"
    echo ""

    # Find repository root
    REPO_ROOT=$(find_repo_root)
    log_info "Target Directory: $REPO_ROOT"

    PIN_FILE="$REPO_ROOT/.taskx-pin"

    # Initialize variables with defaults or existing pin values
    INSTALL_METHOD="git"
    REPO_URL="$DEFAULT_REPO_URL"
    REF="$DEFAULT_REF"
    WHEEL_PATH=""

    if [ -f "$PIN_FILE" ]; then
        log_info "Found existing configuration: $PIN_FILE"
        parse_pin_file "$PIN_FILE"

        # Load existing values
        INSTALL_METHOD="${PIN_INSTALL_METHOD:-$INSTALL_METHOD}"
        REPO_URL="${PIN_REPO_URL:-$REPO_URL}"
        REF="${PIN_REF:-$REF}"
        WHEEL_PATH="${PIN_WHEEL_PATH:-}"
    else
        log_info "No .taskx-pin found. Creating new configuration."
    fi

    # Handle --latest
    if [ "$USE_LATEST" = "true" ]; then
        if [ "$INSTALL_METHOD" != "git" ]; then
            log_error "--latest is only supported for git install method"
            exit 1
        fi

        log_info "Fetching latest tag from $REPO_URL..."
        LATEST_TAG=$(git ls-remote --tags --sort='v:refname' "$REPO_URL" | tail -n1 | sed 's/.*\///')

        if [ -z "$LATEST_TAG" ]; then
            log_error "Could not determine latest tag from $REPO_URL"
            exit 1
        fi

        log_info "Latest version is: $LATEST_TAG"
        REF="$LATEST_TAG"
    fi

    # Handle --version override
    if [ -n "$TARGET_VERSION" ]; then
        REF="$TARGET_VERSION"
        # If user specifies version, assume git install unless wheel path is somehow implied (it's not)
        INSTALL_METHOD="git"
    fi

    # Update/Create pin file if changed or missing
    # Always write to ensure consistency if we are running this script
    write_pin_file "$PIN_FILE" "$INSTALL_METHOD" "$REPO_URL" "$REF" "$WHEEL_PATH"
    echo ""

    # Determine venv location
    if [ -d "$REPO_ROOT/.venv" ]; then
        VENV_PATH="$REPO_ROOT/.venv"
        log_info "Using existing venv: $VENV_PATH"
    else
        VENV_PATH="$REPO_ROOT/.taskx_venv"
        log_info "Creating venv: $VENV_PATH"
        python3 -m venv "$VENV_PATH"
    fi
    echo ""

    # Activate venv
    set +u
    source "$VENV_PATH/bin/activate"
    set -u

    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --quiet --upgrade pip
    echo ""

    # Install TaskX
    if [ "$INSTALL_METHOD" = "git" ]; then
        log_info "Installing TaskX from git:"
        log_info "  Repository: $REPO_URL"
        log_info "  Reference: $REF"

        INSTALL_URL="git+${REPO_URL}@${REF}"

        PIP_ARGS="--upgrade"
        if [ "$FORCE_REINSTALL" = "true" ]; then
            PIP_ARGS="$PIP_ARGS --force-reinstall"
        fi

        pip install $PIP_ARGS "$INSTALL_URL"

    elif [ "$INSTALL_METHOD" = "wheel" ]; then
        # Handle relative paths
        if [[ "$WHEEL_PATH" != /* ]]; then
            WHEEL_PATH="$REPO_ROOT/$WHEEL_PATH"
        fi

        log_info "Installing TaskX from wheel:"
        log_info "  Path: $WHEEL_PATH"

        if [ ! -f "$WHEEL_PATH" ]; then
            log_error "Wheel file not found: $WHEEL_PATH"
            exit 1
        fi

        PIP_ARGS="--upgrade"
        if [ "$FORCE_REINSTALL" = "true" ]; then
            PIP_ARGS="$PIP_ARGS --force-reinstall"
        fi

        pip install $PIP_ARGS "$WHEEL_PATH"
    fi
    echo ""

    # Verify installation
    log_info "Verifying TaskX installation..."

    VERIFICATION_OUTPUT=$(python3 -c "
import sys
import taskx
print(f'Version: {taskx.__version__}')
print(f'Location: {taskx.__file__}')

# Test schema loading
try:
    from taskx.utils.schema_registry import SchemaRegistry
    registry = SchemaRegistry()
    schema = registry.get('allowlist_diff')
    print(f'Schema loading: OK (loaded allowlist_diff)')
except ImportError:
    # Fallback for older versions or if schema registry moved
    print('Schema loading check skipped (SchemaRegistry not found)')
except Exception as e:
    print(f'Schema loading check failed: {e}')
    sys.exit(1)
" 2>&1)

    if [ $? -eq 0 ]; then
        echo "$VERIFICATION_OUTPUT"
        echo ""
        log_info "✅ TaskX installation/upgrade successful!"
        echo ""
        log_info "To activate this environment:"
        log_info "  source $VENV_PATH/bin/activate"
    else
        log_error "Verification failed!"
        echo "$VERIFICATION_OUTPUT"
        exit 1
    fi
}

main "$@"
