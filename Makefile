PYTHON := ./.venv/bin/python

.PHONY: test run query e2e-wiki-sidecar

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	uv run main.py

query:
	uv run query.py "$(QUERY)" --limit $(or $(LIMIT),10) --all-namespaces --json

e2e-wiki-sidecar:
	bash scripts/e2e_wiki_sidecar.sh