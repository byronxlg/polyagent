"""Configuration for trigger worker process."""

import os
from dataclasses import dataclass


@dataclass
class WorkerConfig:
    """Configuration for trigger worker process."""

    # Polling configuration
    poll_interval: float = float(os.getenv("TRIGGER_WORKER_POLL_INTERVAL", "3"))
    error_backoff: float = float(os.getenv("TRIGGER_WORKER_ERROR_BACKOFF", "5"))

    # Logging
    log_level: str = os.getenv("TRIGGER_WORKER_LOG_LEVEL", "INFO")

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.poll_interval < 0.5:
            raise ValueError("poll_interval must be >= 0.5 seconds")
        if self.error_backoff < 1:
            raise ValueError("error_backoff must be >= 1 second")
