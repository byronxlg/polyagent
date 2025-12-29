"""Configuration for trigger worker process."""

import os
from dataclasses import dataclass

# Validation constants
MIN_POLL_INTERVAL = 0.5
MIN_ERROR_BACKOFF = 1


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
        if self.poll_interval < MIN_POLL_INTERVAL:
            msg = f"poll_interval must be >= {MIN_POLL_INTERVAL} seconds"
            raise ValueError(msg)
        if self.error_backoff < MIN_ERROR_BACKOFF:
            msg = f"error_backoff must be >= {MIN_ERROR_BACKOFF} second"
            raise ValueError(msg)
