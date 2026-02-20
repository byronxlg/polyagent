# Test Coverage Analysis

Analysis date: 2025-02-20

## Current State

The project has **111 backend tests** across 14 test files. The frontend has **zero tests** and
no test framework installed.

### Backend Test Inventory

**API tests** (`tests/api/`): 8 files, ~63 tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_agents.py` | 11 | CRUD, list filtering, balance endpoint |
| `test_simulations.py` | 10 | CRUD, delete guards |
| `test_tasks.py` | 8 | CRUD, status filtering |
| `test_agent_tasks.py` | 8 | List, structure, agent filter |
| `test_models.py` | 8 | CRUD, delete guards |
| `test_messages.py` | 7 | List, send, inbox |
| `test_principals.py` | 6 | CRUD, type filter |
| `test_transactions.py` | 4 | List, agent filter |

**Service tests** (`tests/services/`): 6 files, ~48 tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_agent_service.py` | 11 | Get, balance, update profile |
| `test_task_service.py` | 10 | Accept, submit, abandon, accept/deny submission |
| `test_activity_service.py` | 9 | Filtering, pagination, type filters |
| `test_message_service.py` | 7 | Send, inbox, received marking |
| `test_transaction_service.py` | 8 | Balance, grant, deduct, transfer |
| `test_principal_service.py` | 4 | Get, list, filter by type |

---

## Coverage Gaps

### Priority 1 - Backend services with no tests

These services contain significant business logic and have zero test coverage.

**1. ServerService** (`src/services/server_service.py`, ~253 lines)

The MCP server access management layer handles granting/revoking server access for agents,
soft-deleting servers, and building LangChain MCP config dicts. Key untested behaviors:

- `grant_server` idempotency (returns existing grant if already granted)
- `revoke_server` behavior when no grant exists
- `grant_system_servers` idempotency across multiple calls
- Soft-delete: deactivated servers excluded from active lists but remain in database
- `get_server_configs_for_agent` building correct config dict format with `PRINCIPAL_ID` injection
- Server type filtering (system vs custom)

**2. TriggerService** (`src/services/trigger_service.py`, ~371 lines)

Contains four service classes with complex validation and matching logic:

- `TriggerService.create_subscription` rejects duplicates for same agent/table/change_type
- `TriggerService.create_subscription` validates enum values (table name, change type)
- `TriggerEventService.mark_execution_started/completed` with error message truncation
- `EventMatcherService.matches_conditions` - a pure function doing string-equality matching
  on record data, very easy to unit test with high value
- `SimulationConfigService.pause/resume` toggling `is_paused` state

**3. UsageService** (`src/services/usage_service.py`, ~232 lines)

Analytics and aggregation logic:

- `get_model_usage` summary aggregation (total_cost, total_input_tokens, total_output_tokens)
- `get_mcp_usage` tool call counts and 500-character truncation of input/output
- `get_transactions` categorized by direction and reason, with net balance and by_reason summary
- Date range filtering across all three methods
- Agent ID filtering

### Priority 2 - Untested API endpoints

These endpoints exist in `src/api.py` but have no corresponding test coverage.

- **Server endpoints**: `GET /servers`, `GET /servers/{id}`, `GET /servers/{id}/agents`,
  `GET /agents/{id}/servers`
- **Usage endpoints**: `GET /agents/{id}/usage/mcp`, `GET /agents/{id}/usage/model`
- **Trigger endpoints**: `GET /agents/{id}/triggers`, `GET /trigger-events`
- **Activity endpoint**: `GET /activity` with type filtering
- **Simulation lifecycle**: `POST /simulations/{id}/pause`, `POST /simulations/{id}/resume`
- **Agent execution**: `POST /agents/{id}/tick`, `POST /agents/tick-all`
- **Reset endpoint**: `DELETE /reset`

### Priority 3 - Existing test gaps in covered services

Even the tested services have notable gaps:

- **Task multi-agent competition**: Two agents both submit for same task, one is accepted,
  other should become `not_selected`. This is a critical business rule.
- **Agent creation side effects**: Creating an agent should atomically create a principal,
  grant initial balance, grant system MCP servers, and create default trigger subscriptions.
  The API test likely only checks the response, not the side effects.
- **Agent deletion cascade**: `DELETE /agents/{id}` cascades across agent_tasks, triggers,
  trigger_events, usage records, server grants, transactions, and the linked principal. No test
  verifies the cascade completeness.
- **Task status transitions**: The `status` computed property on the Task model (available vs
  expired vs closed) depends on deadline and `accepted_submission_id`. Edge cases around
  exact-deadline timing are untested.

### Priority 4 - Agent system (integration-level)

These modules require LLM and MCP dependencies, making them harder to test, but they contain
critical business logic:

- **Middleware cost calculation** (`src/agent/middleware.py`): `track_model_usage` computes cost
  using `(input_tokens * input_cost + output_tokens * output_cost) / 1_000_000`. The Decimal
  arithmetic and cost deduction flow could be tested with mocked LLM responses.
- **Balance validation**: `validate_and_start` blocks execution when balance is negative.
- **Memory persistence**: `save_reflection_and_stop` saves the last agent message to
  `memory_json`. Verifying the JSON structure would catch serialization bugs.
- **Tool-to-server mapping**: The middleware maps tool names to MCP servers for usage tracking.
  Incorrect mapping would silently attribute usage to the wrong server.

### Priority 5 - MCP servers and trigger worker

These are operational components with no tests:

- **11 MCP server implementations** (~1,600 lines total in `src/mcp_servers/servers/`):
  Each server exposes tools that agents can call. They wrap service layer calls with
  MCP-specific parameter parsing. Testing the parameter validation and error handling
  would catch issues before they reach production.
- **Trigger worker** (`src/worker/trigger_worker.py`, ~345 lines): Polls for database
  changes and fires agent triggers. The matching logic, polling behavior, and error recovery
  are all untested.

### Priority 6 - Frontend (zero coverage)

No test framework is installed. The frontend has ~47 source files including complex logic.

**Highest-value frontend test targets:**

- `lib/utils.ts`: `formatDateTime` and `formatDateTimeShort` have subtle millisecond-appending
  behavior. `cn()` class merging is straightforward to test.
- `lib/api.ts`: ~30 fetch-based API functions with error handling, query parameter construction,
  and typed responses. Mocking `fetch` would cover the entire API client.
- `hooks/useSimulationData.ts`: Pure helper functions (`getStatusColor`, `getAgentName`,
  `getTaskDescription`, `getPrincipalName`) are extractable and unit-testable.
- `components/ActivityFeed.tsx`: Contains an unexported `formatJSON` function with 4 code paths
  handling JSON, Python-dict syntax, and fallback formatting.
- `pages/AgentsPage.tsx`: `agentApprovalRates` calculation divides accepted by total terminal
  statuses - a pure computation with division-by-zero edge cases.
- `pages/HomePage.tsx`: Cents-to-dollars conversion and deadline computation from hours.

**Recommended setup**: Vitest (natural fit with the existing Vite config) plus
`@testing-library/react` for component tests.

---

## Recommended Action Plan

### Phase 1 - Backend service tests (highest ROI)

Add test files for the three untested services. These follow the exact same pattern as the
existing service tests in `tests/services/` and require no new infrastructure.

1. `tests/services/test_server_service.py` - Grant/revoke idempotency, soft-delete, config
   building
2. `tests/services/test_trigger_service.py` - Subscription validation, duplicate rejection,
   `EventMatcherService.matches_conditions` (pure function, trivial to test)
3. `tests/services/test_usage_service.py` - Aggregation accuracy, date filtering, truncation

### Phase 2 - Missing API endpoint tests

Add test files for uncovered endpoints, following the pattern in `tests/api/`:

4. `tests/api/test_servers.py` - Server CRUD and agent-server associations
5. `tests/api/test_activity.py` - Activity feed with type and agent filtering
6. `tests/api/test_triggers.py` - Trigger listing and trigger event listing
7. Extend `tests/api/test_simulations.py` with pause/resume tests

### Phase 3 - Critical business logic edge cases

8. Multi-agent task competition scenario (two submitters, one accepted)
9. Agent creation side-effect verification (principal + balance + servers + triggers)
10. Agent deletion cascade completeness

### Phase 4 - Agent middleware unit tests

11. Cost calculation with mocked model pricing
12. Balance validation blocking execution
13. Memory JSON persistence format

### Phase 5 - Frontend test infrastructure

14. Install Vitest + Testing Library
15. Unit tests for pure utility functions (`formatDateTime`, `cn`, `getStatusColor`)
16. API client tests with mocked `fetch`
17. Component render tests for complex pages (AgentsPage approval rates,
    SimulationSetupPage form validation)
