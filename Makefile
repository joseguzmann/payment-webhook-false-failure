.PHONY: up down test test-docker logs

up:
	docker compose up --build -d
	@echo "Chat: http://localhost:8000"

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	cd api && python -m pytest -q

test-docker:
	docker compose run --rm --no-deps api python -m pytest -q
