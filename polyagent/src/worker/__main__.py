"""Entry point for running the trigger worker as a module.

Usage:
    uv run python -m src.worker
"""

import logging
import sys

from dotenv import load_dotenv

from src.worker.config import WorkerConfig
from src.worker.trigger_worker import TriggerWorker


def main() -> None:
    """Run the trigger worker."""
    # Load environment variables
    load_dotenv()

    # Configure logging
    config = WorkerConfig()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger = logging.getLogger(__name__)
    logger.info("Initializing trigger worker...")

    try:
        worker = TriggerWorker(config)
        worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Worker failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
