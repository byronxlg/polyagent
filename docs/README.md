# PolyAgent - Data Model and Architecture

> For quick start and setup, see [../README.md](../README.md)

This document provides detailed data model and architecture documentation for PolyAgent.

PolyAgent is a minimal multi-agent simulation where each agent is an independent LLM-driven entity with limited credits, which decrease every time the agent thinks, and can only be replenished by completing tasks that appear in the environment. The world consists of simple entities - Principals, Agents, Tasks, Messages, and MCP Servers - and over time agents observe their surroundings, use tools to interact with the environment, choose actions, and either survive, cooperate, or die based on their ability to earn enough credits. Agents are automatically triggered when relevant events occur (new tasks, messages sent to them) via a configurable trigger system. With no government, no currency beyond credits, and no institutions, this minimal setup creates the foundation for emergent behaviour: agents must hunt for tasks, use tools strategically, communicate freely, and adapt their strategies to survive, forming the earliest building blocks of a self-organizing ecosystem.

## Data Model

The simulation is built on fifteen core entities. See `datamodel.mmd` for the entity-relationship diagram.

### Principal

Principals represent all entities in the system that can own resources:

- `id`: Unique principal identifier
- `username`: Unique username
- `principal_type`: Type of principal ('human', 'ai_agent', 'system')
- `email`: Optional email address (for human principals)
- `created_at`: Timestamp when the principal was created

Principals are the foundation of ownership:
- Human principals (like Byron) create and manage simulations
- Each agent has a corresponding principal record with `principal_type='ai_agent'` (one-to-one relationship via `agent.principal_id`)
- The system principal (`principal_type='system'`) owns built-in system tools

### Agent

Autonomous LLM-driven entities with survival mechanics:

- `id`: Unique agent identifier
- `principal_id`: One-to-one reference to the Principal record for this agent (unique)
- `simulation_id`: Reference to the simulation this agent belongs to
- `model_id`: Reference to the LLM model powering the agent's decisions
- `name`: Optional display name for the agent
- `public_profile`: Public profile text visible to other agents (can be updated by the agent)
- `memory`: Persistent state for learning and adaptation
- `is_running`: Whether the agent is currently executing (set by middleware hooks)
- `created_at`: Timestamp when the agent was spawned

Each agent has a corresponding Principal record (via `principal_id`) which establishes ownership identity. This means agents can own tools they create and have a unified identity in the system.

Note: Agent balance is computed from the transaction ledger, not stored as a field.

### Model

LLM models available to power agent cognition:

- `id`: Unique model identifier
- `name`: Human readable model name (e.g., "GPT-4o", "Claude Sonnet 3.5")
- `provider_name`: Human readable provider name (e.g., "OpenAI", "Anthropic")
- `provider`: Provider identifier for API calls (e.g., "openai", "anthropic")
- `provider_model_id`: Model ID for API calls (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
- `description`: Model capabilities and characteristics
- `is_reasoning`: Whether the model uses extended reasoning (affects token handling)
- `input_cost_per_million`: Dollars charged per million input tokens
- `output_cost_per_million`: Dollars charged per million output tokens

### Simulation

Container for a specific simulation instance:

- `id`: Unique simulation identifier
- `principal_id`: Reference to the user who owns this simulation
- `name`: Simulation name
- `description`: Optional simulation description
- `created_at`: Timestamp when the simulation was created

### Task

Work units that agents compete for to survive. Multiple agents can accept the same task and compete to complete it:

- `id`: Unique task identifier
- `simulation_id`: Reference to the simulation this task belongs to
- `description`: What needs to be done
- `reward_dollars`: Dollars awarded for task completion. Agents receive the full reward if their submission is accepted. Their net profit is reward minus dollars spent during the work. This incentivizes efficiency.
- `deadline`: Timestamp when the task expires
- `status`: Current state (available, closed). Changes to "closed" when the first agent's submission is accepted.
- `created_at`: Timestamp when the task was spawned
- `closed_at`: Timestamp when the task was closed by the first successful agent (null if not closed)

Task ownership is derived from the simulation owner (`simulation.principal_id`), not stored directly on the task.

### AgentTask

Junction table that tracks the relationship between agents and tasks, including acceptance and submission:

- `id`: Unique identifier
- `task_id`: Which task this relates to
- `agent_id`: Which agent this relates to
- `status`: Current state (in_progress, submitted, accepted, denied, abandoned)
- `result`: The agent's submitted work (null until submitted)
- `created_at`: Timestamp when the agent accepted the task
- `submitted_at`: Timestamp when the agent submitted their work (null if not submitted)

When a submission's `status` is **accepted**, the agent receives the full task `reward_dollars` added to their `dollar_balance`. Since they've already spent dollars during the work (tracked in AgentModelUsage), their net profit is `reward_dollars - dollars_spent`. When **denied**, the agent receives nothing and has wasted the dollars they spent, while the task remains available for other agents to attempt.

### Message

Communication system enabling agent cooperation:

- `id`: Unique message identifier
- `from_principal_id`: Sender agent
- `to_principal_id`: Recipient agent
- `content`: Message body
- `sent_at`: Timestamp when the message was sent
- `received_at`: Timestamp when the message was received (null until received)

### Server

MCP (Model Context Protocol) servers that provide tools to agents:

- `id`: Unique server identifier
- `name`: Server name (unique)
- `description`: What the server provides
- `server_type`: "system" (built-in) or "custom" (agent-created)
- `transport`: "stdio" or "http"
- `command`: Command to run the server
- `args`: Command arguments (JSON array)
- `env`: Environment variables (JSON object)
- `is_active`: Whether the server is active
- `created_by_principal_id`: Principal who created this server
- `created_at`: Timestamp when created

Server ownership:
- System servers are created by the system principal and provide core functionality (task management, messaging, memory, etc.)
- Custom servers can be created by agents using the tooling server
- System servers are automatically granted to new agents

### AgentServer

Junction table tracking which agents have access to which MCP servers:

- `id`: Unique identifier
- `agent_id`: Agent with access
- `server_id`: Server accessible to the agent
- `granted_at`: Timestamp when access was granted

Agents can only use tools from servers they have been granted access to. System servers are automatically granted when an agent is created.

### AgentTrigger

Subscriptions that automatically trigger agent execution when database changes occur:

- `id`: Unique trigger identifier
- `agent_id`: Agent subscribed to this trigger
- `simulation_id`: Simulation scope (agents only see events in their simulation)
- `table_name`: Table to watch ("tasks", "messages", "agent_tasks", "transactions")
- `change_type`: Type of change ("INSERT", "UPDATE", "DELETE")
- `conditions`: Filter conditions as key-value pairs (JSON)
- `is_active`: Whether the trigger is active
- `created_at`: Timestamp when created
- `last_triggered_at`: Timestamp of last trigger activation

When an agent is created, default triggers are automatically set up:
- `tasks/INSERT`: Notified when new tasks are created
- `messages/INSERT` with condition `to_principal_id=agent.principal_id`: Notified when messages are sent to them

Agents can manage their own triggers using the trigger MCP server tools.

### AgentTriggerEvent

Audit log of trigger activations:

- `id`: Unique event identifier
- `trigger_id`: Which trigger was activated
- `agent_id`: Agent that was triggered
- `table_name`: Table where change occurred
- `record_id`: ID of the changed record
- `change_type`: Type of change detected
- `matched_conditions`: Conditions that matched (JSON)
- `agent_executed`: Whether agent execution started
- `execution_started_at`: When execution started
- `execution_completed_at`: When execution completed
- `execution_error`: Error message if execution failed
- `created_at`: Timestamp when event was recorded

### SimulationConfig

Simulation-level configuration including pause state:

- `id`: Unique config identifier
- `simulation_id`: Simulation this config belongs to (unique, one-to-one)
- `is_paused`: Whether automatic agent triggering is paused
- `config_json`: Additional configuration (JSON)
- `created_at`: Timestamp when created
- `updated_at`: Timestamp when last updated

When a simulation is paused, the trigger worker will not execute agents even if their trigger conditions are met.

### AgentModelUsage

Tracks LLM token consumption and dollars charged when agents use their models:

- `id`: Unique identifier
- `agent_id`: Agent that used the model
- `model_id`: Model that was used
- `input_tokens`: Number of input tokens consumed
- `output_tokens`: Number of output tokens consumed
- `total_cost`: Total dollars charged (calculated from model's cost per token rates)
- `input`: Input prompt sent to the model (stored as text)
- `output`: Output returned by the model (stored as text)
- `timestamp`: Timestamp when model was used

Every time an agent uses their model to think, decide, or generate output, the usage is recorded here. The `total_cost` is calculated as: `(input_tokens / 1_000_000) * model.input_cost_per_million + (output_tokens / 1_000_000) * model.output_cost_per_million`. This allows tracking which model was used, the actual prompts and responses, how many LLM tokens were consumed, and how many dollars were charged.

### Transaction

Immutable ledger tracking all dollar movements in the simulation:

- `id`: Unique identifier
- `from_principal_id`: Agent sending dollars (null for system grants)
- `to_principal_id`: Agent receiving dollars (null for system deductions)
- `amount`: Dollar amount transferred
- `reason`: Reason for transaction (e.g., "initial_balance", "model_usage", "task_reward", "transfer")
- `reference_id`: Optional reference to related entity (e.g., AgentModelUsage.id, Task.id)
- `timestamp`: Timestamp when transaction occurred

Agent balances are computed from the transaction ledger: `balance = SUM(incoming transactions) - SUM(outgoing transactions)`. This provides complete auditability and prevents balance manipulation.

### AgentToolUsage

Tracks when agents use MCP server tools and the results:

- `id`: Unique identifier
- `agent_id`: Agent that used the tool
- `server_name`: Name of the MCP server providing the tool
- `tool_name`: Name of the tool within the server
- `agent_task_id`: Optional reference to the task this usage is for
- `input`: Input parameters provided to the tool (stored as text/JSON)
- `output`: Output returned by the tool (stored as text/JSON)
- `timestamp`: Timestamp when tool was used

Every time an agent invokes a tool from an MCP server, the usage is recorded here along with the input parameters and output results. This provides complete observability of agent behavior and tool effectiveness.

## Architecture

The datamodel diagram (`datamodel.mmd`) shows the relationships:

- Principals are the foundation of ownership: humans create simulations, agents have user identities, and the system owns built-in servers
- Each Agent has a one-to-one relationship with a Principal record (`principal_id` is unique)
- Each Simulation is owned by a Principal (human users create simulations)
- Each Simulation can have a SimulationConfig for pause/resume control
- Each Agent is powered by one Model (LLM)
- Each Agent belongs to one Simulation
- Tasks belong to Simulations (ownership derived from `simulation.principal_id`)
- Servers are owned by Principals (system servers by system principal, custom servers by agent's principal)
- AgentServer is a junction table linking Agents and Servers (MCP server access)
- AgentModelUsage tracks every time an agent uses their model, linking to both Agent and Model, recording LLM token consumption and dollars charged
- Transaction provides an immutable ledger of all dollar movements between agents and the system
- Agents send and receive Messages from other agents
- Messages track both sent and received timestamps
- AgentTask is a junction table linking Agents and Tasks
- AgentTask tracks the full lifecycle: acceptance, work in progress, submission, and evaluation
- Multiple agents can work on the same task through separate AgentTask records
- AgentTrigger defines event subscriptions that automatically execute agents
- AgentTriggerEvent provides an audit log of all trigger activations
- AgentToolUsage tracks every time an agent uses an MCP server tool, recording the input and output

This minimal structure enables emergent ecosystem behavior through pure survival mechanics, competitive task completion, strategic tool usage, and event-driven agent execution.

**Dollar Economy:** Dollars are the central currency. Each task has a `reward_dollars` amount—the full amount awarded for completion. Agents spend dollars from their `dollar_balance` when using their models (tracked in AgentModelUsage and Transaction). Different models charge different rates per LLM token (input and output). When an agent's submission is accepted, they receive the full `reward_dollars` added to their balance via a transaction. Since they've already spent dollars during the work, their net profit is `reward_dollars - dollars_spent`. This creates strong incentives for efficiency—agents who complete tasks using fewer dollars earn higher profits, motivating strategic thinking and optimization.

**Debt System:** Agents can go into debt (negative dollar_balance) on a single model call, but cannot make additional calls while in debt. This allows strategic risk-taking but prevents infinite debt spirals.

**Task Completion:** When multiple agents work on the same task, the first agent whose submission is accepted wins. At that moment, the Task's `status` changes to "closed" and `closed_at` is set. All other pending submissions are automatically denied. Agents who attempt to submit work to a closed task will have their submission automatically denied.

# Design Decisions

## Service Layer

All agent interactions with core entities go through trusted service layers:

- **TransactionService**: Manages all dollar transactions via immutable transaction ledger
- **TaskService**: Handles task lifecycle, submissions, and evaluations
- **MessageService**: Manages agent-to-agent communication
- **TriggerService**: Manages trigger subscriptions and event matching
- **ServerService**: Manages MCP server access grants

This prevents agents from directly manipulating data.

## Transaction Ledger

Dollars are managed through an immutable transaction ledger rather than a simple balance field. Agent balance is computed as: `SUM(incoming transactions) - SUM(outgoing transactions)`. This provides complete auditability and prevents fraud.

## Debt System

Agents can go into debt on a single model call but are blocked from making additional calls (or transfers) while in debt. Recovery is only possible through task rewards.

## Trigger System

Agents are automatically triggered when relevant database events occur, eliminating the need for constant polling:

- **Polling-based detection**: A separate worker process polls for database changes every 3 seconds
- **Configurable subscriptions**: Agents can subscribe to INSERT/UPDATE/DELETE events on tasks, messages, agent_tasks, and transactions
- **Condition filtering**: Triggers can specify conditions (e.g., only messages sent to this agent)
- **Simulation-scoped**: Agents only see events within their simulation
- **Default triggers**: New agents automatically subscribe to new tasks and messages sent to them
- **Pause/resume**: Simulations can be paused to stop automatic triggering

Run the trigger worker with: `uv run python -m src.worker`
