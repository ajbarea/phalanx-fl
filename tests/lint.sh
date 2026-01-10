#!/bin/sh
# Python code quality and testing script
# Usage: ./lint.sh [--test] [--sonar]

. "$(dirname "$0")/scripts/common.sh"
navigate_to_root

setup_unicode_env
setup_logging_with_file "tests/logs" "lint"

if ! ensure_virtual_environment; then
    log_error "Please run './reinstall_requirements.sh' first."
    exit 1
fi

TEST_MODE=false
SONAR_MODE=false
for arg in "$@"; do
    case $arg in
        --test) TEST_MODE=true ;;
        --sonar) SONAR_MODE=true ;;
    esac
done

if [ "$TEST_MODE" = true ] || [ "$SONAR_MODE" = true ]; then
    install_requirements
fi

log_info "⚡ Running ruff check..."
ruff check --fix src tests

log_info "⚡ Running isort..."
isort --quiet src tests

log_info "⚡ Running ruff format..."
ruff format src tests

log_info "✨ Running frontend linting..."
cd frontend && npm run lint && npm run format -- --log-level warn && cd ..

log_info "🔍 Running mypy..."
mypy --config-file=pyproject.toml

if command_exists pyright; then
    log_info "🔍 Running pyright..."
    pyright src/ tests/
else
    log_warning "Pyright not found. Skipping. To install: npm install -g pyright"
fi

run_pytest_suite() {
    log_info "🧪 Running unit tests in parallel (xdist)..."
    run_python -m coverage erase
    run_python -m coverage run --append --source=src -m pytest -n auto tests/unit/ --tb=short

    log_info "🧪 Running integration tests serially..."
    run_python -m coverage run --append --source=src -m pytest tests/integration/ --tb=short

    log_info "🧪 Running performance tests serially..."
    run_python -m coverage run --append --source=src -m pytest tests/performance/ --tb=short

    log_info "📊 Generating coverage reports..."
    run_python -m coverage xml -o "$LOG_DIR/coverage.xml"
    run_python -m coverage html -d "$LOG_DIR/coverage_html"
    run_python -m coverage report --skip-covered
}

if [ "$TEST_MODE" = true ]; then
    run_pytest_suite
fi

if [ "$SONAR_MODE" = true ]; then
    [ "$TEST_MODE" = false ] && run_pytest_suite
    log_info "🔍 Running SonarQube analysis..."
    ./tests/scripts/sonar.sh
fi

echo ""
log_info "🏁 Linting and testing process finished."
log_info "📝 Full log saved to: $LOG_FILE"
if [ "$TEST_MODE" = true ] || [ "$SONAR_MODE" = true ]; then
    log_info "📊 Coverage reports saved to: $LOG_DIR/coverage.xml and $LOG_DIR/coverage_html/"
fi
