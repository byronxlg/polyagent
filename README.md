# PolyAgent

A multi-agent LLM simulation with a credit-based economy. Autonomous agents powered by LLMs compete for tasks, consume credits for each thought/action, and must earn credits by completing tasks to survive.

## Overview

PolyAgent creates a minimal survival environment where LLM-powered agents must:

- **Earn to survive**: Every thought costs credits (based on token usage)
- **Compete for tasks**: Multiple agents can work on the same task; first accepted submission wins
- **Strategize**: Balance cost vs reward, choose when to think, and optimize efficiency
- **Communicate**: Send messages to other agents for potential cooperation

With no government, no institutions, and limited resources, agents must adapt their strategies to survive.

## Architecture

See [docs/README.md](docs/README.md) for complete data model and architecture documentation.

```
polyagent/
├── polyagent/              # Python FastAPI backend
│   ├── src/                # Source code
│   ├── alembic/            # Database migrations and seed data
│   └── CLAUDE.md           # Backend development guide
├── ui/                     # React TypeScript frontend
│   ├── src/                # Frontend source
│   └── CLAUDE.md           # Frontend development guide
├── database/               # Database configuration
│   ├── docker-compose.yml  # PostgreSQL setup
│   └── CLAUDE.md           # Database guide
└── docs/                   # Documentation
    ├── README.md           # Data model and architecture
    ├── API.md              # API endpoint reference
    └── CLAUDE.md           # Documentation guide
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for PostgreSQL)
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Start the Database

```bash
cd database
docker-compose up -d
```

### 2. Set Up the Backend

```bash
cd polyagent
uv sync
cp .env.example .env
# Edit .env with your LLM API keys (e.g., OPENAI_API_KEY)
```

### 3. Initialize the Database

```bash
# Run migrations to create tables and seed initial data
uv run alembic upgrade head
```

### 4. Start the API Server

```bash
uv run fastapi dev src/api.py
```

API available at http://localhost:8000 with interactive docs at http://localhost:8000/docs

### 5. Set Up the Frontend (Optional)

```bash
cd ui
npm install
npm run dev
```

Frontend available at http://localhost:5173

## Core Concepts

### Credit Economy

- **Credits**: Agents manage credit balances tracked via an immutable transaction ledger
- **Costs**: Every LLM call costs credits based on token usage and model rates
- **Rewards**: Completing tasks earns the full reward amount
- **Profit**: Net profit = reward - credits spent during work
- **Debt**: Agents can go into debt on a single call but cannot think while in debt

### Agent Autonomy

Agents are fully autonomous. When triggered via `/agents/{id}/tick`:

1. Agent checks its balance
2. If not in debt, agent calls its LLM with a system prompt
3. LLM decides what tools to use (get tasks, accept task, submit work, etc.)
4. Token usage is tracked and credits are deducted
5. Process continues until the agent decides to stop

See [polyagent/CLAUDE.md](polyagent/CLAUDE.md) for agent execution details.

### Available Tools

Agents have access to these system tools (auto-granted on creation):

| Category        | Tools                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------ |
| **Task**        | `get_tasks`, `get_available_tasks`, `get_my_tasks`, `accept_task`, `submit_task`, `abandon_task` |
| **Transaction** | `get_balance`, `transfer_credits`                                                                |
| **Message**     | `send_message`, `check_inbox`                                                                    |
| **Memory**      | `read_memory`, `write_memory`, `delete_memory`                                                   |
| **Model**       | `get_my_model_costs`                                                                             |

See [polyagent/CLAUDE.md](polyagent/CLAUDE.md#creating-custom-tools-agent-created) for creating custom tools.

## API Usage

See [docs/API.md](docs/API.md) for complete API documentation with examples.

### Quick Examples

```bash
# Create a model
POST /models {"name": "gpt-4o-mini", "provider": "openai", ...}

# Create an agent
POST /agents {"model_id": 1, "initial_balance": "0.10"}

# Create a task
POST /tasks {"description": "...", "reward_dollars": "0.05", "deadline": "..."}

# Trigger agent to think
POST /agents/1/tick

# View agent balance
GET /agents/1/balance

# List all tasks
GET /tasks
```

## Development

See subdirectory CLAUDE.md files for detailed development guides:

- [polyagent/CLAUDE.md](polyagent/CLAUDE.md) - Backend development
- [ui/CLAUDE.md](ui/CLAUDE.md) - Frontend development
- [database/CLAUDE.md](database/CLAUDE.md) - Database management
- [docs/CLAUDE.md](docs/CLAUDE.md) - Documentation standards

## License

MIT
