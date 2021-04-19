.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: test
test:
	pytest --cov=tcintercom

.PHONY: format
format:
	isort -w 120 tcintercom
	isort -w 120 tests
	black -S -l 120 --target-version py38 tcintercom tests

.PHONY: lint
lint:
	flake8 tests/ tcintercom/

