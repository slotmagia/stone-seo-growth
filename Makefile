.PHONY: dev test lint smoke

dev:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest -q

smoke:
	python -m compileall -q app
