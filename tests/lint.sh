#!/bin/bash
# Run Python code quality checks and tests with coverage reporting.
#
# Performs linting (ruff, isort), type checking (mypy, pyright), and
# frontend linting. Optionally runs the full test suite with coverage
# and SonarQube analysis.
#
# Usage: ./tests/lint.sh [OPTIONS]
#
# Options:
#   --test   Run pytest suite with coverage (unit, integration, performance)
#   --sonar  Run SonarQube analysis (implies --test if not already run)
#
# Examples:
#   ./tests/lint.sh              # Linting and type checking only
#   ./tests/lint.sh --test       # Linting + full test suite with coverage
#   ./tests/lint.sh --sonar      # Linting + tests + SonarQube analysis
#   ./tests/lint.sh --test --sonar  # Same as --sonar alone
#
# Dependencies: ruff, isort, mypy, npm (for frontend), pytest, coverage
# Optional: pyright (npm install -g pyright), sonar-scanner (for --sonar)

. "$(dirname "$0")/scripts/common.sh"
navigate_to_root

setup_unicode_env
setup_logging_with_file "tests/logs" "lint"

if [ -n "${LOG_FILE:-}" ]; then
    export LOG_CAPTURE_ALL_OUTPUT=true
    exec > >(tee -a "$LOG_FILE") 2>&1
fi

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

# Install dependencies only when running tests to avoid unnecessary work
# during quick lint-only runs.
if [ "$TEST_MODE" = true ] || [ "$SONAR_MODE" = true ]; then
    install_requirements
fi

log_info "⚡ Running ruff check..."
ruff check --fix intellifl tests

log_info "⚡ Running isort..."
isort --quiet intellifl tests

log_info "⚡ Running ruff format..."
ruff format intellifl tests

log_info "✨ Running frontend linting..."
cd frontend && npm run lint && npm run format -- --log-level warn && cd ..

log_info "🔍 Running mypy..."
run_python -m mypy --config-file=pyproject.toml

if command_exists pyright; then
    log_info "🔍 Running pyright..."
    pyright intellifl/ tests/
else
    log_warning "Pyright not found. Skipping. To install: npm install -g pyright"
fi

# Run the full pytest suite with coverage collection.
#
# Executes tests in three phases with different parallelization strategies:
# - Unit tests: parallel (xdist) for speed since they're isolated
# - Integration tests: serial to avoid resource conflicts between tests
# - Performance tests: serial to get accurate timing measurements
#
# Globals:
#   LOG_DIR: Directory for coverage output files
run_pytest_suite() {
    # Unit tests run in parallel - they're isolated and benefit from xdist.
    log_info "🧪 Running unit tests in parallel (xdist)..."
    run_python -m coverage erase
    run_python -m coverage run --append --source=intellifl -m pytest -n auto tests/unit/ --tb=short

    # Integration tests run serially to avoid port conflicts, database locks,
    # and other shared resource issues.
    log_info "🧪 Running integration tests serially..."
    run_python -m coverage run --append --source=intellifl -m pytest tests/integration/ --tb=short

    # Performance tests run serially to ensure accurate timing measurements
    # without interference from parallel test execution.
    log_info "🧪 Running performance tests serially..."
    run_python -m coverage run --append --source=intellifl -m pytest tests/performance/ --tb=short

    log_info "📊 Generating coverage reports..."
    run_python -m coverage xml -o "$LOG_DIR/coverage.xml"
    run_python -m coverage html -d "$LOG_DIR/coverage_html"
    run_python -m coverage report --skip-covered
}

if [ "$TEST_MODE" = true ]; then
    run_pytest_suite
fi

if [ "$SONAR_MODE" = true ]; then
    # Run tests first if not already run - SonarQube needs coverage data.
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
