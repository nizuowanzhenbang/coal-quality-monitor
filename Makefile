.PHONY: dev-backend dev-frontend seed test install

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

seed:
	cd backend && python seed_data.py

test:
	cd backend && pytest tests/ -v

build:
	cd frontend && npm run build
