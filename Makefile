# make install   set up the Python venv and npm packages
# make dev       run backend (:8000) and frontend (:5173) together
# make test      run pytest
# make eval      run the offline evaluation and write backend/evaluation/report.md

ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python
else
PY := backend/.venv/bin/python
endif

.PHONY: install dev backend frontend test eval data

install:
	python -m venv backend/.venv
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 backend frontend

test:
	cd backend && ../$(PY) -m pytest -q

eval:
	cd backend && ../$(PY) -m evaluation.evaluate

data:
	python data/generate_data.py
