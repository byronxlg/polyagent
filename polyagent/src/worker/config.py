"""Configuration for trigger worker process."""

import os
from dataclasses import dataclass


@dataclass
class WorkerConfig:
    """Configuration for trigger worker process."""

    # Polling configuration
    poll_interval: float = float(os.getenv("TRIGGER_WORKER_POLL_INTERVAL", "3"))
    error_backoff: float = float(os.getenv("TRIGGER_WORKER_ERROR_BACKOFF", "5"))

    # Execution limits
    max_agents_per_cycle: int = int(os.getenv("TRIGGER_WORKER_MAX_AGENTS_PER_CYCLE", "10"))

    # Logging
    log_level: str = os.getenv("TRIGGER_WORKER_LOG_LEVEL", "INFO")

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.poll_interval < 0.5:
            raise ValueError("poll_interval must be >= 0.5 seconds")
        if self.max_agents_per_cycle < 1:
            raise ValueError("max_agents_per_cycle must be >= 1")
        if self.error_backoff < 1:
            raise ValueError("error_backoff must be >= 1 second")
