# Plan: Tool Designations & Agent-Created Tools

## Part 1: Tool Designation System

### Proposed Designations

| Designation | Scope | Description | Examples |
|-------------|-------|-------------|----------|
| `local` | Agent | Tools that only affect the calling agent | `read_memory`, `write_memory`, `delete_memory` |
| `internal` | System | Tools that interact with the simulation | `get_tasks`, `accept_task`, `submit_task`, `send_message`, `transfer_dollars`, `get_balance` |
| `external` | External Services | Tools that call external APIs | `web_search`, `web_fetch` |
| `custom` | Agent-Created | Tools written by agents at runtime | `read_collective_memory`, `write_collective_memory` |

### Suggestions for 3rd Party Categories

| Designation | Scope | Description | Examples |
|-------------|-------|-------------|----------|
| `mcp` | MCP Servers | Tools provided by Model Context Protocol servers | Tools from connected MCP servers |
| `integration` | Third-Party APIs | Pre-built integrations with external services | `send_sms` (Twilio), `create_github_issue`, `send_email` |
| `community` | Shared/Imported | Tools imported from other agent systems or shared repos | Tools from a tool marketplace |

### Updated Tools Table

```sql
tools
  id: int (PK)
  name: str (unique)
  description: str
  designation: str  -- 'local', 'internal', 'external', 'custom', 'mcp', 'integration'
  category: str     -- grouping within designation (e.g., 'task', 'message', 'transaction')
  is_default: bool  -- auto-grant to new agents
  created_at: datetime
  created_by_agent_id: int (FK, nullable)  -- for custom tools
```

### Current Tools Mapping

| Tool | Current Category | New Designation | New Category |
|------|-----------------|-----------------|--------------|
| `read_memory` | memory | local | memory |
| `write_memory` | memory | local | memory |
| `delete_memory` | memory | local | memory |
| `get_tasks` | task | internal | task |
| `get_available_tasks` | task | internal | task |
| `get_my_tasks` | task | internal | task |
| `accept_task` | task | internal | task |
| `submit_task` | task | internal | task |
| `abandon_task` | task | internal | task |
| `send_message` | message | internal | message |
| `check_inbox` | message | internal | message |
| `transfer_dollars` | transaction | internal | transaction |
| `get_balance` | transaction | internal | transaction |
| `get_my_model_costs` | model | internal | model |

### Implementation Tasks - Tool Designations

- [ ] Add `designation` column to `tools` table (default: 'internal')
- [ ] Add `created_at` column to `tools` table
- [ ] Add `created_by_agent_id` column to `tools` table (nullable)
- [ ] Add migration to `init_db()` for new columns
- [ ] Update existing tools with correct designations
- [ ] Update `ToolResponse` schema to include designation
- [ ] Update UI to show tool designations

---

## Part 2: Agent-Created Tools (Custom Designation)

### Architecture

```
src/agent/tools/
  __init__.py
  task_tool.py          # designation: internal
  message_tool.py       # designation: internal
  memory_tool.py        # designation: local
  transaction_tool.py   # designation: internal
  model_tool.py         # designation: internal
  custom/               # designation: custom (agent-created)
    __init__.py
    collective_memory_tool.py
```

### How Custom Tools Work

1. Agent calls `create_tool_file` with tool definitions and code
2. System generates Python module in `src/agent/tools/custom/`
3. Tool discovery picks it up, registers with `designation='custom'`
4. `created_by_agent_id` tracks which agent created it
5. Tools persist as files, survive restarts

### New Agent Tools for Tool Creation

**`create_tool_file`** - Write a new custom tool module
```python
def create_tool_file(
    module_name: str,
    tools: list[dict]
) -> dict
```

**`list_custom_tools`** - List agent-created tools
```python
def list_custom_tools() -> dict
```

**`read_tool_file`** - View source of a custom tool
```python
def read_tool_file(module_name: str) -> dict
```

### Example: Collective Memory

```python
create_tool_file(
    module_name="collective_memory",
    tools=[
        {
            "name": "write_collective_memory",
            "description": "Write to shared memory all agents can access",
            "parameters": [
                {"name": "key", "type": "str", "description": "The key"},
                {"name": "value", "type": "str", "description": "The value"}
            ],
            "code": '''
from datetime import datetime
session = SessionLocal()
try:
    entry = session.query(CollectiveMemory).filter(CollectiveMemory.key == key).first()
    if entry:
        entry.value = value
        entry.updated_by_agent_id = agent_id
        entry.updated_at = datetime.utcnow()
    else:
        entry = CollectiveMemory(key=key, value=value, created_by_agent_id=agent_id,
                                  updated_by_agent_id=agent_id, created_at=datetime.utcnow(),
                                  updated_at=datetime.utcnow())
        session.add(entry)
    session.commit()
    return {"success": True, "key": key}
except Exception as e:
    session.rollback()
    return {"success": False, "error": str(e)}
finally:
    session.close()
'''
        },
        {
            "name": "read_collective_memory",
            "description": "Read from shared memory by key",
            "parameters": [
                {"name": "key", "type": "str", "description": "The key to read"}
            ],
            "code": '''
session = SessionLocal()
try:
    entry = session.query(CollectiveMemory).filter(CollectiveMemory.key == key).first()
    if entry:
        return {"success": True, "key": key, "value": entry.value, "updated_by": entry.updated_by_agent_id}
    return {"success": False, "error": f"Key '{key}' not found"}
finally:
    session.close()
'''
        }
    ]
)
```

### Implementation Tasks - Custom Tools

#### Phase 1: Data Model
- [ ] Create `collective_memory` table and model
- [ ] Add migration to `init_db()`
- [ ] Create `src/agent/tools/custom/` directory with `__init__.py`

#### Phase 2: Tool File Generator
- [ ] Create `CustomToolGenerator` class
- [ ] Generate valid Python modules from tool definitions
- [ ] Validate syntax before writing
- [ ] Update `ToolService._discover_all_tools()` to scan custom directory

#### Phase 3: Agent Tools
- [ ] Create `custom_tool.py` with create/list/read tools
- [ ] Register custom tools with `designation='custom'`
- [ ] Track `created_by_agent_id`

---

## Summary

**Phase 1**: Update tools table with designation system
**Phase 2**: Implement custom tool creation (file-based)
**Phase 3**: Future - MCP integration, third-party integrations
