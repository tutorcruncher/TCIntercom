.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: test
test:
	pytest tests/

.PHONY: lint
lint:
	flake8 tests/ app/
	black  tests/ app/
	isort  -rc -w 120 tests/
	isort  -rc -w 120 app/

