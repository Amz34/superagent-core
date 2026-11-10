.PHONY: all test lint clean run

all: lint test

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m py_compile superagent_core/*.py tests/*.py

clean:
	rm -rf __pycache__ superagent_core/__pycache__ tests/__pycache__ .superagent .pytest_cache

run:
	python3 -m superagent_core.cli --help
