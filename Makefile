.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: test
test:
	pytest tests/

.PHONY: format
format:
	isort -rc -w 120 app
	isort -rc -w 120 tests
	black -S -l 120 --target-version py38 app tests

.PHONY: lint
lint:
	flake8 tests/ app/

