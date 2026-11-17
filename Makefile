PYTHON ?= python3
.PHONY: doctor init db-up migrate seed api-dev web-dev dev preview-local lint typecheck test test-unit test-integration test-sqlite test-web e2e eval-mock eval-live smoke live-smoke build ci contract
doctor init db-up migrate seed api-dev web-dev dev preview-local lint typecheck test test-unit test-integration test-sqlite test-web e2e eval-mock eval-live smoke live-smoke build ci contract:
	$(PYTHON) scripts/tasks.py $@
