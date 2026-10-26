# One-command workflows. On Windows use the PowerShell steps in README.md instead.
VENV ?= .venv
PY   := $(VENV)/bin/python

.PHONY: setup run test web serve clean

setup:  ## Create a virtualenv, install dependencies and create .env
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	@test -f .env || (cp .env.example .env && echo "Created .env: add your OPENAI_API_KEY")

run:  ## Launch the Streamlit app at http://localhost:8501
	$(PY) -m streamlit run app.py

test:  ## Run the test suite (no API key needed)
	$(PY) -m pytest

web:  ## Build the standalone browser app (pixelforge.html)
	python3 scripts/build_web.py

serve:  ## Serve the browser app at http://localhost:8000
	python3 -m http.server 8000

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
