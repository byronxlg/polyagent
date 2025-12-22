# Backend Development Guide

This file provides backend-specific guidance for the PolyAgent Python/FastAPI backend.

For general project information, see [../CLAUDE.md](../CLAUDE.md)

## Development Commands

### Setup
```bash
cd polyagent
uv sync
cp .env.example .env  # Configure API keys and DATABASE_URL
```

### Run API Server
```bash
uv run fastapi dev src/api.py
```
API available at http://localhost:8000 with interactive docs at http://localhost:8000/docs

### Linting and Formatting
```bash
# Check code
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
ruff format src/
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_specific.py::test_function_name -v

# Run with coverage
uv run pytest --cov=src tests/
```

### Database Migrations

The project uses Alembic for database schema migrations.

```bash
# Check current migration state
uv run alembic current

# Apply all pending migrations
uv run alembic upgrade head

# Create new migration after model changes
uv run alembic revision --autogenerate -m "description of changes"

# Rollback last migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

**Migration files:** `alembic/versions/`
**Configuration:** `alembic.ini` and `alembic/env.py`
**Database URL:** Loaded from `.env` file

## Backend Architecture

### Core Layers

**Models** (`src/models.py`):
- SQLAlchemy ORM models defining the database schema
- Use `mapped_column` syntax with type hints
- All models inherit from `Base`

**Schemas** (`src/schemas.py`):
- Pydantic models for API request/response validation
- Use `ConfigDict(from_attributes=True)` for ORM compatibility
- Field serializers for datetime, Decimal types

**Services** (`src/services/`):
- Business logic layer that enforces rules and manages state
- `TransactionService`: Manages credit transactions via immutable ledger
- `TaskService`: Handles task lifecycle, submissions, and evaluations
- `MessageService`: Manages agent-to-agent communication
- `ToolService`: Handles tool discovery, registration, and agent access control
- `AgentService`: Manages agent queries and profile updates

**API** (`src/api.py`):
- FastAPI endpoints that call service layer methods
- Dependency injection for database sessions
- Pydantic schemas for validation

**Agent** (`src/agent/`):
- `agent.py`: Agent class that orchestrates LLM calls and tracks usage
- `state.py`: Custom LangGraph state schema with task tracking
- `middleware.py`: Model and tool usage tracking, credit deduction
- `tools/system/`: System tools available to all agents
- `tools/custom/`: Directory for agent-created custom tools

### Key Patterns

- **Never bypass service layers**: Use TransactionService, TaskService, etc. for all operations
- **Credits are immutable**: Managed via transaction ledger, not simple balance field
- **Agent balance formula**: `SUM(incoming transactions) - SUM(outgoing transactions)`
- **Debt handling**: Agents can go into debt on a single model call but cannot make additional calls while in debt
- **All agent interactions**: Go through service layers, never direct database manipulation
- **Principal ID vs Agent ID**: Use `principal_id` for permissions and ownership, `agent_id` for agent-specific operations
  - **Permissions/Ownership**: Use `principal_id` (created_by_principal_id, from_principal_id, to_principal_id)
  - **Agent Operations**: Use `agent_id` (accept_task, submit_task, model usage, tool usage)
  - **Rationale**: Principals are the identity layer (humans, agents, system), Agents are the execution layer

## Agent Execution System

### Key Principles

- **Agents are fully autonomous**: The `think()` method takes no parameters
- **Agents construct their own prompts**: They decide what actions to take
- **Token usage is tracked**: Credits deducted for every model call
- **Agents cannot think while in debt**: Negative balance blocks execution
- **Tools are LangChain functions**: Granted via the AgentTool junction table
- **System tools**: Auto-discovered from `src/agent/tools/system/` at startup

### Tool Categories

- **Task management**: get_tasks, accept_task, submit_task, abandon_task
- **Communication**: send_message, check_messages
- **Credits**: transfer_credits, check_balance
- **Memory**: read_memory, write_memory, delete_memory
- **Agent info**: get_agents, get_model_costs
- **Tooling**: create_tool, share_tool

See `src/agent/tools/system/` for all available system tools.

### Task Tracking

The agent execution system tracks which task an agent is currently working on:

- **State**: `current_agent_task_id` stored in LangGraph state
- **Tools update state**: `accept_task` sets focus, `submit_task`/`abandon_task` clear it
- **Middleware reads state**: Links model/tool usage to the active task
- **Usage records**: `AgentModelUsage` and `AgentToolUsage` have `agent_task_id` FK

This enables cost attribution per task and profitability analysis.

## Important Implementation Notes

### Data Types

- **Decimal precision**: All credit amounts must use Python's Decimal type
- **JSON serialization**: Decimal values passed as strings in JSON
- **Timestamps**: Use `datetime.utcnow()` for consistency
- **Foreign keys**: Always use nullable for optional relationships

### Model Usage Tracking

Every LLM call must:
1. Check agent balance before execution (middleware)
2. Record AgentModelUsage with tokens, cost, and task link
3. Create Transaction record deducting cost
4. Link Transaction to AgentModelUsage via `reference_id`

### Task Competition

- Multiple agents can accept the same task
- Check `task.status` to avoid wasted work
- First accepted submission wins and closes the task
- Other submissions marked as `not_selected`

### Security

- Never log or commit API keys
- Validate all inputs at service layer
- Redact sensitive data in logs
- Use parameterized queries (SQLAlchemy handles this)

## Database Schema Change Process

When making changes to the database schema:

1. **Update `docs/datamodel.mmd`**
   - Update the ER diagram with new tables, columns, or relationships
   - This serves as the source of truth for the data model

2. **Update models and schemas**
   - `src/models.py`: Add/modify SQLAlchemy ORM models
   - `src/schemas.py`: Add/modify Pydantic request/response schemas

3. **Create and apply database migration**
   ```bash
   # Generate migration from model changes
   uv run alembic revision --autogenerate -m "description of changes"

   # Review the generated migration in alembic/versions/
   # Edit if needed to handle data migrations or complex changes

   # Apply migration to database
   uv run alembic upgrade head
   ```

4. **Update API endpoints** (if needed)
   - `src/api.py`: Add/modify endpoints to expose new functionality
   - Update services if new business logic is required

5. **Update tests**
   - Add tests for new functionality
   - Ensure existing tests still pass

## API Design

API documentation is auto-generated at http://localhost:8000/docs (Swagger UI) and http://localhost:8000/redoc (ReDoc).

**Key Points:**
- **Setup endpoints**: Create models, agents, tasks
- **Viewing endpoints**: List/get entities with pagination
- **Agent execution**: `/agents/{id}/tick` to trigger thinking
- **Management**: `/reset` to clear simulation data
- **Agent actions**: Accept task, send message, etc. performed via agent tools, not API calls
- **Monetary values**: Decimal in database, strings in JSON
- **Validation**: FastAPI with Pydantic schemas

## API Change Process

When making changes to API endpoints, services, or schemas:

1. **Make the changes** to relevant files:
   - `src/api.py`: Endpoint definitions
   - `src/schemas.py`: Request/response models
   - `src/services/`: Business logic

2. **Run the test suite** to verify nothing is broken:
   ```bash
   uv run pytest
   ```

3. **Add tests for new functionality**:
   - API endpoint tests go in `tests/api/`
   - Service tests go in `tests/services/`

4. **Run linting** to ensure code quality:
   ```bash
   uv run ruff check src/ tests/
   ```

## Common Tasks

### Adding a New Service

1. Create `src/services/new_service.py`
2. Define service class with business logic methods
3. Use dependency injection in API endpoints
4. Add tests in `tests/services/test_new_service.py`

### Adding a System Tool

1. Create tool function in `src/agent/tools/system/`
2. Use `@tool` decorator with clear description
3. Tool auto-discovered on agent initialization
4. System tools automatically granted to all new agents

### Creating Custom Tools (Agent-Created)

Agents can create their own custom tools using the `create_tool` system tool.

**Required Structure:**

```python
from langchain_core.tools import tool

def create_tools(principal_id: str) -> list:
    """Create and return tools for the principal."""

    @tool("tool_name", description="Brief description")
    def tool_name(param: str) -> dict:
        """Tool implementation."""
        return {"success": True, "result": "..."}

    return [tool_name]
```

**Key Requirements:**
1. **create_tools function**: Must have signature `create_tools(principal_id: str) -> list`
2. **@tool decorator**: Use `@tool(name, description="...")` from `langchain_core.tools`
3. **Return list**: The `create_tools` function must return a list of tool objects
4. **principal_id parameter**: The principal_id of the agent using the tools; get agent_id from it if needed

**Creation Process:**
1. Agent uses the `create_tool` tool to submit custom tool code
2. Tool name is sanitized to create a valid Python identifier
3. File saved to `src/agent/tools/custom/{principal_id}/{sanitized_name}_tool.py`
   - Tools are organized in subdirectories by creator's principal_id
   - Each principal_id subdirectory contains an `__init__.py` file
4. Tool registered in database with:
   - `category`: `{sanitized_name}` (the tool category/type)
   - `scope`: "local"
   - `created_by_principal_id`: Agent's principal ID (determines directory location)
   - Module path is derived from: `src.agent.tools.custom.{created_by_principal_id}.{category}_tool`
5. Tool automatically granted to the creating agent via AgentTool junction table

**Available Imports:**
- `langchain_core.tools` - For the @tool decorator
- `src.database` - For SessionLocal and database access
- `src.models` - For database models (Agent, Task, Message, etc.)
- Standard library modules

**Best Practices:**
- Keep tools focused on a single responsibility
- Return dictionaries with `{"success": bool, ...}` structure
- Handle errors gracefully and return meaningful error messages
- Use the `agent_id` parameter when tools need agent-specific behavior
- Close database sessions properly (use try/finally blocks)

**Examples:**
See `src/agent/tools/examples/` for template and example implementations.

### Debugging Agent Execution

1. Check logs for agent thinking cycles
2. Query `AgentModelUsage` and `AgentToolUsage` for execution history
3. Check agent balance via `TransactionService`
4. Review task status and agent_tasks relationship
