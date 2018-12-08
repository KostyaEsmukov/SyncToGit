

.PHONY: format
format:
	isort -rc synctogit tests *.py

.PHONY: lint
lint:
	flake8 && isort --check-only -rc synctogit tests *.py

.PHONY: test
test:
	coverage run -m py.test
	coverage report

.PHONY: clean
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	rm -Rf dist
	rm -Rf *.egg-info

.PHONY: docs
docs:
	make -C docs html

.PHONY: check-docs
check-docs:
	# Doesn't generate any output but prints out errors and warnings.
	make -C docs dummy
