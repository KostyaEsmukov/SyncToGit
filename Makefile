

.PHONY: lint
lint:
	flake8 && isort --check-only -rc synctogit *.py

.PHONY: clean
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	rm -Rf dist
	rm -Rf *.egg-info

.PHONY: format
format:
	isort -rc synctogit *.py
