APP_NAME := pardarshi
PORT := 8000

# ── Dev ──────────────────────────────────────────────

.PHONY: install
install: ## Install all dependencies (including dev)
	uv sync --all-extras

.PHONY: dev
dev: ## Run dev server with hot reload
	uv run uvicorn app.main:app --reload --port $(PORT)

.PHONY: test
test: ## Run test suite
	uv run pytest -v

.PHONY: lint
lint: ## Run ruff linter (if installed)
	uv run ruff check app/ tests/

.PHONY: fmt
fmt: ## Run ruff formatter (if installed)
	uv run ruff format app/ tests/

# ── Docker ───────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build Docker image
	docker build -t $(APP_NAME) .

.PHONY: docker-run
docker-run: ## Run container (detached)
	docker run -d --name $(APP_NAME) -p $(PORT):8000 $(APP_NAME)

.PHONY: docker-stop
docker-stop: ## Stop and remove container
	docker stop $(APP_NAME) && docker rm $(APP_NAME)

.PHONY: docker-logs
docker-logs: ## Tail container logs
	docker logs -f $(APP_NAME)

.PHONY: docker-shell
docker-shell: ## Shell into running container
	docker exec -it $(APP_NAME) bash

# ── Help ─────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
