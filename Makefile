.PHONY: up down test lint demo-reset secret-scan

up:
	docker compose up --build -d

down:
	docker compose down -v

test:
	python -m pytest tests/ -v --tb=short

lint:
	python -m flake8 . --max-line-length=120 --exclude=.git,__pycache__,models/all-MiniLM-L6-v2,darklabdoc,venv,env
	python -m bandit -r . -ll --exclude=./models/all-MiniLM-L6-v2,./darklabdoc,./venv,./tests

secret-scan:
	@echo "Scanning for secrets..."
	@python -c "import subprocess; result = subprocess.run(['git', 'log', '-p', '--all'], capture_output=True, text=True); lines = [l for l in result.stdout.split('\n') if any(kw in l.lower() for kw in ['password', 'secret', 'api_key', 'token', 'private_key']) and l.startswith('+')]; print('\n'.join(lines) if lines else 'No secrets found.')"

demo-reset:
	@echo "Resetting demo environment..."
	rm -f scraper/darkweb_intel.db darkweb_intel.db
	python db_setup.py
	python run_pipeline.py
	@echo "Demo environment reset complete."
