PYTHON := ./.venv/bin/python

.PHONY: test run query service maintain smoke-e2e e2e-wiki-sidecar

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	$(PYTHON) main.py

query:
	$(PYTHON) query.py "$(QUERY)" --limit $(or $(LIMIT),10) --all-namespaces --json

service:
	$(PYTHON) service.py

maintain:
	$(PYTHON) maintenance.py --json

smoke-e2e:
	RUN_BRIDGE_E2E_SMOKE=1 $(PYTHON) -m unittest tests.test_smoke_e2e -v

e2e-wiki-sidecar:
	bash scripts/e2e_wiki_sidecar.sh