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

## Language-Specific Standards

### Python
- Line length: 112 characters
- Python 3.11+ required
- Type annotations required (enforced by ruff)
- Use Decimal type for all monetary amounts
- Follow ruff linting rules (comprehensive configuration)

### TypeScript
- ESLint configured with TypeScript strict mode
- Use React 19 patterns
- Prefer functional components with hooks

## Git Workflow

**Always use feature branches for changes. Never commit directly to main.**

### Making Changes (Slash Commands)

Two slash commands handle the full workflow from idea to parallel agent:

**`/issue <description>`** - Draft and create a GitHub issue

```
/issue add rate limiting to the API
```

Claude drafts a structured issue (title, background, requirements, acceptance
criteria) and creates it via `gh issue create`. Use this from any Claude Code
session, including mobile.

**`/start-issue <number>`** - Spin up an isolated agent for an issue

```
/start-issue 42
```

Claude fetches the issue, creates a worktree (`../polyagent-issue-<N>-<slug>`),
and opens a new tmux window with Claude Code pre-loaded with the issue context.
Multiple issues can run as parallel agents in separate windows.

**Cleanup** after a PR is merged:
```bash
git worktree remove ../polyagent-issue-<N>-<slug>
git branch -d feature/issue-<N>-<slug>
```

### Quick Reference

```bash
# List worktrees
git worktree list

# Remove a worktree after merge
git worktree remove ../polyagent-issue-<N>-<slug>
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

### Commenting on Pull Requests

When leaving comments on PRs (reviews, issue comments, or general feedback):

1. **Structured Format**: Use clear headers and bullet points. Keep comments focused and scannable.

2. **Reply Threading**: When addressing a specific comment or issue raised by someone, use `gh api` to reply to that comment rather than creating a new top-level comment:
   ```bash
   # Reply to a specific comment
   gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_ID/replies \
     -f body="Your reply here"
   ```

3. **Wait for CI**: Before claiming a fix is complete, wait for GitHub Actions to pass:
   ```bash
   # Check workflow status
   gh run list --limit 5

   # Watch a specific run
   gh run watch RUN_ID
   ```
   Only state something is "fixed" after CI confirms it passes.

4. **Signature**: End all PR comments with the Claude Code signature:
   ```
   ---
   Generated with [Claude Code](https://claude.com/claude-code)
   ```

5. **Concise Updates**: Avoid overly verbose explanations. State what changed and why briefly.

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
   docker compose up -d
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

### UI Testing via Chrome

Use the Chrome browser automation tools to test UI functionality:

1. **Navigate to the UI** at http://localhost:5173
2. **Select a simulation** from the sidebar
3. **Test agent details**:
   - Click on an agent to view their profile
   - Check the "Servers" tab shows granted MCP servers
   - Check the "Usage" tab shows model usage history
4. **Test agent execution**:
   - Click the "Run" button on an agent detail page
   - Verify the agent's balance decreases after execution
   - Check that new usage entries appear in the Usage tab
5. **Verify data refresh**:
   - Click "Refresh Data" in the sidebar
   - Confirm updated balances and transaction counts

### Database Queries

For direct database inspection:
```bash
# Check servers table
PGPASSWORD=agent psql -h localhost -U agent -d polyagent -c "SELECT name, server_type FROM servers;"

# Check agent server grants
PGPASSWORD=agent psql -h localhost -U agent -d polyagent -c "SELECT * FROM agent_servers LIMIT 10;"
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
