# Daily Efficiency Coach (Backend)

FastAPI + MongoDB backend for tasks, habits, and habit logs.

## Run locally
1) Start Mongo (Docker):
   docker run -d --name mongo -p 27017:27017 mongo:latest

2) Create venv + install:
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

3) Create .env:
   cp .env.example .env

4) Run API:
   uvicorn app.main:app --reload

Docs:
http://127.0.0.1:8000/docs