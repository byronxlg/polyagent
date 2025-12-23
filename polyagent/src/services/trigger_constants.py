"""Shared constants for trigger system."""

# Tables that agents can subscribe to for change notifications
WATCHABLE_TABLES = frozenset({"tasks", "messages", "agent_tasks", "transactions"})

# Valid change types for trigger subscriptions
CHANGE_TYPES = frozenset({"INSERT", "UPDATE", "DELETE"})
