# AI Incident Response Agent
 
An automated AI agent that triages, analyzes, and mitigates infrastructure incidents. Built with **FastAPI**, **LangGraph**, and **SQLAlchemy**, and evaluated using an **LLM-as-a-judge** framework powered by Langfuse.
 
---
 
## Table of Contents
 
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Environment Setup](#1-environment-setup)
  - [2. Install Dependencies](#2-install-dependencies)
  - [3. Start the Database](#3-start-the-database)
  - [4. Run the Application](#4-run-the-application)
- [Evaluation & Metrics](#evaluation--metrics)
  - [Core Metrics](#core-metrics)
  - [Running Evaluations](#running-evaluations)
- [Tech Stack](#tech-stack)
---
 
## Prerequisites
 
Ensure the following are installed on your Windows machine before getting started:
 
| Tool | Purpose |
|---|---|
| [Python 3.11+](https://www.python.org/downloads/) | Runtime |
| [Poetry](https://python-poetry.org/docs/#installation) | Dependency management |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the PostgreSQL database |
 
---
 
## Getting Started
 
### 1. Environment Setup
 
This project uses **split environment files**. Because Docker Compose and the FastAPI app resolve file paths differently on Windows, you must maintain **both** `.env` and `.env.development` in the project root with identical database credentials.
 
Create both files and populate them as follows:
 
```env
# Database
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
 
# Application
ENV=development
OPENAI_API_KEY=your_openai_api_key_here
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key_here
LANGFUSE_SECRET_KEY=your_langfuse_secret_key_here
LANGFUSE_HOST=https://us.cloud.langfuse.com
```
 
> **Note:** Never commit these files to version control. Ensure `.env` and `.env.development` are listed in your `.gitignore`.
 
---
 
### 2. Install Dependencies
 
```cmd
poetry install
```
 
---
 
### 3. Start the Database
 
Make sure Docker Desktop is running, then spin up the PostgreSQL container:
 
```cmd
docker-compose down
docker-compose up -d db
```
 
---
 
### 4. Run the Application
 
Start the FastAPI development server:
 
```cmd
poetry run uvicorn app.main:app --reload
```
 
Once running, the interactive API documentation (Swagger UI) is available at:
 
**http://127.0.0.1:8000/docs**
 
---
 
## Evaluation & Metrics
 
The project includes an **LLM-as-a-judge** evaluation suite powered by [Langfuse](https://langfuse.com) to monitor and grade agent response quality over time.
 
### Core Metrics
 
| Metric | Description |
|---|---|
| **Conciseness** | Checks that the agent responds without unnecessary rambling |
| **Hallucination** | Detects fabricated system logs or non-existent errors |
| **Helpfulness** | Verifies that mitigation steps are clear and actionable |
| **Relevancy** | Confirms the response directly addresses the reported incident |
| **Toxicity** | Flags unsafe or unprofessional language |
 
### Running Evaluations
 
> **Before running evals**, send a few test messages through the `/api/v1/chat` endpoint in Swagger UI to populate your Langfuse dashboard with interaction traces.
 
Since `make` is not natively available on Windows, run the evaluation module directly:
 
```cmd
set ENV=development&& poetry run python evals/main.py --quick
```
 
The evaluation script retrieves real historical traces from Langfuse and grades them against the metrics above.
 
---
 
## Tech Stack
 
- **[FastAPI](https://fastapi.tiangolo.com/)** — API framework
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — Agent orchestration
- **[SQLAlchemy](https://www.sqlalchemy.org/)** — ORM and database management
- **[PostgreSQL](https://www.postgresql.org/)** — Primary data store (via Docker)
- **[Langfuse](https://langfuse.com/)** — LLM observability and evaluation
- **[Poetry](https://python-poetry.org/)** — Python dependency management
