# Canva-NotebookLM Agent

A powerful integration agent bridging Canva and NotebookLM, designed to enhance AI-powered design workflows. This project features a modern architecture with a FastAPI backend and a React (Vite) frontend.

## 🚀 Features

- **AI Integration**: Seamlessly connects with NotebookLM for advanced content processing.
- **Design Automation**: Integrates with Canva to streamline design creation.
- **Modern Stack**: Built with high-performance technologies.
- **Scalable**: Dockerized and Kubernetes-ready.

## 🛠️ Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (AsyncPG), Pydantic
- **Frontend**: React, Vite, TailwindCSS (assumed standard)
- **Database**: PostgreSQL
- **Caching**: Redis
- **Infra**: Docker, Kubernetes, Alembic for migrations

## 📦 Project Structure

```
├── src/                # Backend application code
├── ui/                 # Frontend React application
├── documents/          # Document storage
├── docker/             # Docker configuration files
├── k8s/                # Kubernetes manifests
├── alembic/            # Database migrations
├── tests/              # Test suite
├── scripts/            # Helper scripts
└── Makefile           # Project management commands
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL & Redis (or use Docker)

### Backend Setup

1. **Create Virtual Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -e .[dev]
   ```

3. **Configure Environment**:
   Copy `.env.example` (if available) or create `.env` with necessary credentials.

4. **Run Server**:
   ```bash
   uvicorn src.main:app --reload
   ```

### Frontend Setup

1. **Navigate to UI**:
   ```bash
   cd ui
   ```

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Run Dev Server**:
   ```bash
   npm run dev
   ```

## 🐳 Docker Support

Run the entire stack using Docker Compose:

```bash
docker-compose up -d --build
```

## 🧪 Testing

Run backend tests:
```bash
pytest
```

Run frontend tests:
```bash
cd ui && npm run e2e
```

## 📄 License

MIT License. See `pyproject.toml` for details.
