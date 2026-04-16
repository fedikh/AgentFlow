# AgentFlow — FastAPI Backend

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Edit `.env` with your PostgreSQL credentials:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/agentflow
SECRET_KEY=your-secret-key
```

## Run

```bash
uvicorn app.main:app --reload
```

API available at: http://localhost:8000
Swagger docs at:  http://localhost:8000/docs

## Endpoints

| Method | URL               | Description        |
|--------|-------------------|--------------------|
| POST   | /api/auth/register | Sign up            |
| POST   | /api/auth/login    | Login              |