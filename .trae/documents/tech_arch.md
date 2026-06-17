
## 1. Architecture Design

Frontend (React + TypeScript + Vite) -> Backend (FastAPI + JWT) -> Data (PostgreSQL + Redis + RabbitMQ)

## 2. Technology Description

### Frontend
- React@18 + TypeScript
- Vite@6
- Ant Design@5
- Zustand (state management)
- React Router DOM@6
- Recharts (charts)
- Lucide React (icons)
- Axios (HTTP client)
- Tailwind CSS@3

### Backend
- FastAPI@0.104+
- JWT Authentication (python-jose + passlib)
- SQLAlchemy@2 + PostgreSQL
- Redis
- Celery + RabbitMQ

## 3. Route Definitions

| Route | Purpose | Protected |
|-------|---------|-----------|
| /login | Login page | No |
| / | Dashboard | Yes |
| /evaluators | Evaluator management | Yes |
| /models | Model comparison | Yes |
| /records | Evaluation records | Yes |
| /cost | Cost monitoring | Yes |
| /health | System health | Yes |

## 4. API Definitions

### Authentication
- POST /api/v1/auth/login - Login
- POST /api/v1/auth/refresh - Refresh token

### Dashboard
- GET /api/v1/dashboard/stats - Dashboard statistics

### Evaluators
- GET /api/v1/evaluators - List evaluators
- GET /api/v1/evaluators/{name} - Get evaluator detail

### Models
- GET /api/v1/models - List models
- POST /api/v1/models/compare - Compare models

### Evaluations
- POST /api/v1/evaluate - Sync evaluate
- POST /api/v1/evaluate/async - Async evaluate
- GET /api/v1/records - List records

### Cost
- GET /api/v1/cost - Cost metrics

### Health
- GET /api/v1/health/detailed - Detailed health
- GET /api/v1/metrics - Performance metrics

## 5. Server Architecture

FastAPI Router -> Authentication Middleware -> Services Layer -> Domain Layer -> Infrastructure Layer -> Database/Redis/RabbitMQ

## 6. Data Model

### Users Table
- id (PK), username (UK), email, password_hash, role, created_at, updated_at

### Evaluation Records Table
- id (PK), user_id (FK), case_id, adapter_name, model_name, status, score, latency_ms, created_at, updated_at

## 7. CORS Configuration

Development: http://localhost:5173
Production: https://dashboard.aieval.example.com

## 8. Frontend Project Structure

frontend/
 src/
    components/ (Layout, Dashboard, Evaluators, Models, Common)
    pages/ (Login, Dashboard, Evaluators, Models, Records, Cost, Health)
    hooks/ (useAuth, useApi)
    services/ (api.ts)
    stores/ (authStore.ts)
    types/ (index.ts)
    utils/ (index.ts)
    App.tsx, main.tsx, index.css
 public/, index.html
 package.json, vite.config.ts, tsconfig.json, tailwind.config.js, postcss.config.js
