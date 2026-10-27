.PHONY: up down test logs

up:
	docker compose up --build -d
	@echo "Chat: http://localhost:8000"

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	cd api && python -m pytest -q
