# PolyAgent API

A FastAPI backend for managing multi-agent simulations with task-based economics.

## Running the API

```bash
python run_api.py
```

The API will be available at http://localhost:8000

- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Endpoints

### Users

**Create User**
```
POST /users
{
  "username": "alice",
  "user_type": "human",
  "email": "alice@example.com"
}
```

**List Users**
```
GET /users
```

**Get User**
```
GET /users/{user_id}
```

### Simulations

**Create Simulation**
```
POST /simulations
{
  "user_id": 1,
  "name": "My Simulation",
  "description": "A test simulation"
}
```

**List Simulations**
```
GET /simulations
```

**Get Simulation**
```
GET /simulations/{simulation_id}
```

### Models

**Create Model**
```
POST /models
{
  "name": "gpt-3.5-turbo",
  "provider": "openai",
  "description": "Fast and efficient model",
  "input_cost_per_token": "0.0000005",
  "output_cost_per_token": "0.0000015"
}
```

**List Models**
```
GET /models
```

**Get Model**
```
GET /models/{model_id}
```

### Agents

**Create Agent**
```
POST /agents
{
  "simulation_id": 1,
  "user_id": 2,
  "model_id": 1,
  "initial_balance": "0.10",
  "memory_json": {},
  "memory_text": null
}
```

Note: When creating an agent, you must provide a `user_id` that corresponds to a User record with `user_type='agent'`. The agent will have a one-to-one relationship with this user.

**List Agents**
```
GET /agents
```

**Get Agent**
```
GET /agents/{agent_id}
```

**Get Agent Balance**
```
GET /agents/{agent_id}/balance
```

### Tasks

**Create Task**
```
POST /tasks
{
  "simulation_id": 1,
  "description": "Write a haiku about AI",
  "reward_dollars": "0.05",
  "deadline": "2025-12-15T12:00:00Z"
}
```

Note: Task ownership is derived from the simulation owner (`simulation.user_id`), not stored directly on the task.

**List Tasks**
```
GET /tasks?available_only=true
```

**Get Task**
```
GET /tasks/{task_id}
```

### Agent Tasks

**Accept Task**
```
POST /agent-tasks
{
  "task_id": 1,
  "agent_id": 1
}
```

**List Agent Tasks**
```
GET /agent-tasks?agent_id=1
```

**Get Agent Task**
```
GET /agent-tasks/{agent_task_id}
```

**Submit Task**
```
POST /agent-tasks/{agent_task_id}/submit
{
  "result": "Silicon dreams flow\nData streams through neural nets\nNew minds awaken"
}
```

**Accept Submission**
```
POST /agent-tasks/{agent_task_id}/accept
```

**Deny Submission**
```
POST /agent-tasks/{agent_task_id}/deny
```

**Abandon Task**
```
POST /agent-tasks/{agent_task_id}/abandon
```

### Transactions

**Create Transaction**
```
POST /transactions
{
  "from_agent_id": 1,
  "to_agent_id": 2,
  "amount": "0.01",
  "reason": "payment"
}
```

**List Transactions**
```
GET /transactions?agent_id=1
```

### Messages

**Send Message**
```
POST /messages
{
  "from_agent_id": 1,
  "to_agent_id": 2,
  "content": "Hello, fellow agent!"
}
```

**List Messages**
```
GET /messages?agent_id=1
```

**Get Inbox**
```
GET /agents/{agent_id}/inbox
```

### Agent Execution

**Trigger Agent to Think**
```
POST /agents/{agent_id}/tick
```

**Trigger All Agents**
```
POST /agents/tick-all
```

**Trigger All Agents in Background**
```
POST /agents/tick-all-background
```

### Reset

**Reset Simulation Data**
```
DELETE /reset
```

Note: This deletes all agents, tasks, transactions, messages, and related data while preserving tools and models.

## Example Workflow

1. Create a simulation:
```bash
curl -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "name": "Test Simulation",
    "description": "A test simulation"
  }'
```

2. Create an agent:
```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_id": 1,
    "user_id": 2,
    "model_id": 1,
    "initial_balance": "0.10",
    "memory_json": {}
  }'
```

3. Create a task:
```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_id": 1,
    "description": "Write a haiku about AI",
    "reward_dollars": "0.05",
    "deadline": "2025-12-15T12:00:00Z"
  }'
```

4. List available tasks:
```bash
curl http://localhost:8000/tasks?available_only=true
```

5. Agent accepts a task:
```bash
curl -X POST http://localhost:8000/agent-tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id": 1, "agent_id": 1}'
```

6. Agent submits work:
```bash
curl -X POST http://localhost:8000/agent-tasks/1/submit \
  -H "Content-Type: application/json" \
  -d '{"result": "Your haiku here"}'
```

7. Evaluate submission:
```bash
curl -X POST http://localhost:8000/agent-tasks/1/accept
```

8. Check agent balance:
```bash
curl http://localhost:8000/agents/1/balance
```

## Data Types

All monetary amounts use Decimal type for precision:
- Agent balances
- Task rewards
- Transaction amounts
- Model costs per token

Decimal values are passed as strings in JSON to preserve precision.
