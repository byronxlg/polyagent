# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PolyAgent is a multi-agent LLM simulation with a credit-based economy. Autonomous agents powered by LLMs compete for tasks, consume credits for each thought/action, and must earn credits by completing tasks to survive.

**Architecture:**
- **Backend:** Python FastAPI with SQLAlchemy ORM, PostgreSQL database
- **Frontend:** React 19 + TypeScript + Vite with Tailwind CSS
- **Agent System:** LangGraph-based autonomous agents with tool access
- **Economy:** Credit-based with immutable transaction ledger

## Subdirectory Documentation

For detailed information specific to each part of the project, see:

- **[polyagent/CLAUDE.md](polyagent/CLAUDE.md)** - Backend development, API, agent system, database migrations
- **[ui/CLAUDE.md](ui/CLAUDE.md)** - Frontend development, React components, styling
- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Documentation standards, diagrams, API docs
- **[database/CLAUDE.md](database/CLAUDE.md)** - Database setup, schema, PostgreSQL configuration

## Universal Code Standards

### Naming and Style
- **KISS**: Keep It Simple. Favor simple, maintainable solutions over clever code
- **YAGNI**: You Ain't Gonna Need It. Don't implement features until actually needed
- **DRY**: Don't Repeat Yourself. Extract repeated logic into utility functions
- **Naming**: Use descriptive, self-documenting names. Prefer clarity over brevity
- **Comments**: Explain "why" decisions were made, not "what" the code does

### Code Quality
- **Function Size**: Keep functions small and focused on a single task
- **Fail Fast**: Validate inputs early and fail immediately with clear errors
- **Security**: Never log/commit secrets, validate all inputs, redact sensitive data in logs
- **Error Handling**: Handle errors gracefully with meaningful, actionable messages
- **Testing**: Add tests following existing project patterns before marking work complete
- **Changes**: Make minimal, focused changes that solve one problem at a time

### Python-Specific
- Line length: 112 characters
- Python 3.11+ required
- Type annotations required (enforced by ruff)
- Use Decimal type for all monetary amounts
- Follow ruff linting rules (comprehensive configuration)

### TypeScript-Specific
- ESLint configured with TypeScript strict mode
- Use React 19 patterns
- Prefer functional components with hooks

## Communication Style

- **No Emojis**: Never use emojis in code, comments, commit messages, or documentation
- **No Em Dashes**: Avoid em dashes in writing; use hyphens or restructure sentences
- **Clarity**: Write in clear, direct language without unnecessary embellishment
- **Review First**: When asked to review or analyze, do that first and report findings before making changes

## Git Workflow

**Always use feature branches for changes. Never commit directly to main.**

### Making Changes (Worktrees)

Use git worktrees for isolated feature development. This allows parallel Claude sessions without conflicts.

1. **Create a worktree** for your feature:
   ```bash
   # From the main repo directory
   git worktree add ../polyagent-<short-description> -b feature/<short-description>
   cd ../polyagent-<short-description>
   ```

2. **Work in the worktree** - make changes and commits

3. **Push and create a PR** when ready:
   ```bash
   git push -u origin feature/<short-description>
   gh pr create --fill
   ```

4. **Cleanup** after PR is merged:
   ```bash
   cd ../polyagent  # Return to main repo
   git worktree remove ../polyagent-<short-description>
   git branch -d feature/<short-description>
   ```

### Quick Reference

```bash
# List worktrees
git worktree list

# Create worktree with new branch
git worktree add ../polyagent-foo -b feature/foo

# Remove worktree after merge
git worktree remove ../polyagent-foo
```

### Branch Naming

- `feature/<description>` - New features or enhancements
- `fix/<description>` - Bug fixes
- `docs/<description>` - Documentation changes
- `refactor/<description>` - Code refactoring

### PR Guidelines

- Use `gh pr create` to open pull requests
- PRs should have a clear title and description
- Link to any related issues if applicable

## High-Level Architecture

### Backend (polyagent/)
- **Models** (`src/models.py`): SQLAlchemy ORM defining database schema
- **Schemas** (`src/schemas.py`): Pydantic models for API validation
- **Services** (`src/services/`): Business logic layer
- **API** (`src/api.py`): FastAPI endpoints
- **Agent** (`src/agent/`): LangGraph-based autonomous agents

### Frontend (ui/)
- React 19 with TypeScript
- Vite build system
- Tailwind CSS v4 styling
- Radix UI component primitives
- Dark mode by default

### Key Concepts
- **Credits Economy**: Immutable transaction ledger tracks all credit movements
- **Tool System**: System tools vs custom tools, access controlled per agent
- **Task Competition**: Multiple agents can work on same task; first accepted submission wins
- **Agent Autonomy**: Agents decide their own actions via LangGraph tools

## Getting Started

1. **Database Setup:**
   ```bash
   cd database
   docker-compose up -d
   ```

2. **Backend Setup:**
   ```bash
   cd polyagent
   uv sync
   uv run python -m alembic upgrade head  # Apply database migrations
   ```

3. **Frontend Setup:**
   ```bash
   cd ui
   npm install
   ```

See subdirectory CLAUDE.md files for detailed development workflows.

## Local Testing

Use tmux to run multiple services simultaneously for local testing.

### Starting Services

1. **Start the API server** (in one tmux pane):
   ```bash
   cd polyagent
   uv run python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
   ```
   API available at http://localhost:8000 with docs at http://localhost:8000/docs

2. **Start the UI server** (in another tmux pane):
   ```bash
   cd ui
   npm run dev
   ```
   UI available at http://localhost:5173

### Testing Agent Execution

To test an agent's think cycle via the API:
```bash
# Get list of agents
curl -s http://localhost:8000/agents | python3 -m json.tool

# Trigger agent think cycle
curl -s -X POST "http://localhost:8000/agents/<agent-id>/tick" | python3 -m json.tool

# Check agent's granted MCP servers
curl -s "http://localhost:8000/agents/<agent-id>/servers" | python3 -m json.tool
```

### Database Queries

For direct database inspection:
```bash
# Check servers table
PGPASSWORD=agent psql -h localhost -U agent -d agent_civilisation -c "SELECT name, server_type FROM servers;"

# Check agent server grants
PGPASSWORD=agent psql -h localhost -U agent -d agent_civilisation -c "SELECT * FROM agent_servers LIMIT 10;"
```

### Tmux Quick Reference

```bash
# List sessions
tmux list-sessions

# Send command to a pane
tmux send-keys -t <session>:<window>.<pane> '<command>' Enter

# Capture pane output (for logs)
tmux capture-pane -t <session>:<window>.<pane> -p -S -50
```
