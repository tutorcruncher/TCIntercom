.PHONY: install
install:
	pip install -r requirements.txt
	pip install devtools

.PHONY: test
test:
	pytest --cov=tcintercom

.PHONY: format
format:
	ruff check --fix .
	ruff format .

.PHONY: lint
lint:
	ruff check .
	ruff format --check .

.PHONY: web
web:
	python3 tcintercom/run.py web
