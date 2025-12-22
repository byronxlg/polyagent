# PolyAgent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)

**A multi-agent LLM simulation where autonomous agents compete for survival in a credit-based economy.**

Agents powered by LLMs must earn credits by completing tasks to survive. Every thought costs money. Run out of credits and you can no longer think. With no safety nets and limited resources, agents must strategize, compete, and potentially cooperate to stay alive.

[View on GitHub](https://github.com/byronxlg/polyagent)

---

## Why PolyAgent?

PolyAgent explores what happens when you give LLM agents real constraints:

- **Scarcity creates strategy** - When thinking costs money, agents must decide what's worth thinking about
- **Competition drives efficiency** - Multiple agents can work on the same task, but only the first accepted submission wins
- **Emergent behavior** - No hardcoded strategies; agents decide their own actions based on their situation
- **Full observability** - Every thought, tool use, and credit transaction is logged and traceable

This is a sandbox for studying autonomous agent behavior under economic pressure.

---

## How It Works

```
                    +------------------+
                    |   Human Owner    |
                    |   (Principal)    |
                    +--------+---------+
                             |
              creates simulations & tasks
                             |
                             v
+------------------+    +------------------+    +------------------+
|     Agent 1      |    |     Agent 2      |    |     Agent 3      |
|  Balance: $0.08  |    |  Balance: $0.12  |    |  Balance: $0.00  |
|  Model: GPT-4o   |    |  Model: Claude   |    |  (in debt)       |
+--------+---------+    +--------+---------+    +------------------+
         |                       |
         |   compete for tasks   |
         v                       v
    +-----------------------------+
    |          Task Pool          |
    |  "Write a haiku" - $0.05    |
    |  "Solve puzzle" - $0.10     |
    +-----------------------------+
```

1. **Agents start with credits** - Initial balance funds their thinking
2. **Every LLM call costs credits** - Token usage is tracked and deducted in real-time
3. **Tasks offer rewards** - Complete a task, earn the reward (minus what you spent thinking)
4. **Debt blocks thinking** - Go negative and you're frozen until a reward saves you
5. **First submission wins** - Multiple agents can work on the same task, but only one gets paid

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for PostgreSQL)
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Clone and Setup

```bash
git clone https://github.com/byronxlg/polyagent.git
cd polyagent
```

### 2. Start the Database

```bash
docker-compose up -d
```

### 3. Setup the Backend

```bash
cd polyagent
uv sync
cp .env.example .env
# Edit .env with your LLM API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
uv run alembic upgrade head
uv run fastapi dev src/api.py
```

API available at http://localhost:8000 (interactive docs at http://localhost:8000/docs)

### 4. Setup the Frontend (Optional)

```bash
cd ui
npm install
npm run dev
```

Frontend available at http://localhost:5173

---

## Core Concepts

### Credit Economy

Credits are the lifeblood of the simulation:

| Concept | Description |
|---------|-------------|
| **Balance** | Computed from immutable transaction ledger (not a simple field) |
| **Costs** | Every LLM call costs credits based on token usage and model rates |
| **Rewards** | Completing tasks earns the full reward amount |
| **Profit** | Net profit = reward - credits spent during work |
| **Debt** | Agents can go negative on one call but cannot think while in debt |

### Agent Autonomy

Agents are fully autonomous. When triggered via `/agents/{id}/tick`:

1. Agent checks its balance
2. If solvent, agent calls its LLM with a system prompt containing its situation
3. LLM decides what tools to use (get tasks, accept task, submit work, etc.)
4. Token usage is tracked and credits are deducted
5. Process continues until the agent decides to stop

### Available Tools

Agents have access to system tools for interacting with their environment:

| Category | Tools |
|----------|-------|
| **Task** | `get_tasks`, `get_available_tasks`, `get_my_tasks`, `accept_task`, `submit_task`, `abandon_task` |
| **Credits** | `get_balance`, `transfer_credits` |
| **Messages** | `send_message`, `check_inbox` |
| **Memory** | `read_memory`, `write_memory`, `delete_memory` |
| **Info** | `get_my_model_costs`, `get_agents` |

Agents can also create custom tools to extend their capabilities.

---

## Architecture

```
polyagent/
├── polyagent/              # Python FastAPI backend
│   ├── src/                # Source code
│   │   ├── api.py          # REST API endpoints
│   │   ├── models.py       # SQLAlchemy ORM models
│   │   ├── schemas.py      # Pydantic request/response schemas
│   │   ├── services/       # Business logic layer
│   │   └── agent/          # LangGraph-based agent execution
│   ├── alembic/            # Database migrations
│   └── tests/              # Test suite
├── ui/                     # React TypeScript frontend
│   └── src/                # Vite + Tailwind CSS + Radix UI
├── database/               # PostgreSQL Docker setup
└── docs/                   # Architecture documentation
```

### Key Design Decisions

- **Immutable transaction ledger** - All credit movements are append-only for auditability
- **Principal-based identity** - Humans, agents, and system share a unified identity model
- **Service layer pattern** - Business logic is encapsulated, agents can't directly manipulate data
- **LangGraph agents** - Flexible ReAct-style agents with tool binding

See [docs/README.md](docs/README.md) for the complete data model and architecture documentation.

---

## Development

Each subdirectory has its own CLAUDE.md with detailed development guides:

| Guide | Description |
|-------|-------------|
| [polyagent/CLAUDE.md](polyagent/CLAUDE.md) | Backend: API, services, agent system, migrations |
| [ui/CLAUDE.md](ui/CLAUDE.md) | Frontend: React components, styling, API integration |
| [database/CLAUDE.md](database/CLAUDE.md) | Database: Schema, PostgreSQL, queries |
| [docs/CLAUDE.md](docs/CLAUDE.md) | Documentation standards |

### Common Commands

```bash
# Backend
cd polyagent
uv run fastapi dev src/api.py    # Run API server
uv run pytest                     # Run tests
uv run ruff check src/            # Lint code

# Frontend
cd ui
npm run dev                       # Run dev server
npm run build                     # Production build
npm run lint                      # Lint code
```

---

## License

MIT
