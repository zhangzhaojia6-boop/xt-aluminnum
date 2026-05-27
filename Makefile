.PHONY: clean clean-pyc clean-test clean-build help

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "clean-build - remove build artifacts"

clean: clean-pyc clean-test clean-build

clean-pyc:
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*~' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '*.egg-info' -exec rm -rf {} +

clean-test:
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.pytest-cache' -exec rm -rf {} +
	find . -type d -name 'test-results' -exec rm -rf {} +
	find . -type d -name 'playwright-report' -exec rm -rf {} +
	rm -rf backend/.tmp-pytest/
	rm -rf backend/.pytest-run-*/
	rm -rf backend/pytest-cache-files-*/

clean-build:
	rm -rf frontend/dist/
	rm -rf frontend/node_modules/.vite/
	rm -rf .codegraph/
	rm -f local-dev.db
	rm -f backend/local-dev.db
	rm -f backend/test_migration_chain.db
	rm -f backend/.codex-preview.db
