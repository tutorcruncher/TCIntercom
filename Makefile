.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: test
test:
	pytest --cov=tcsupport

.PHONY: format
format:
	isort -w 120 tcsupport
	isort -w 120 tests
	black -S -l 120 --target-version py38 tcsupport tests

.PHONY: lint
lint:
	flake8 tests/ tcsupport/

