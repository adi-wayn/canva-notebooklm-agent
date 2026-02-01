"""Worker entry point with proper logging configuration."""
import asyncio
import logging
import sys
from src.workers.workflow_worker import run_worker_loop


def setup_logging():
    """Configure logging for worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Ensure our modules are at INFO
    logging.getLogger("src.workers").setLevel(logging.INFO)
    logging.getLogger("src.infra").setLevel(logging.INFO)
    logging.getLogger("src.orchestration").setLevel(logging.INFO)


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("🚀 Starting Workflow Worker")
    logger.info("=" * 80)
    
    try:
        asyncio.run(run_worker_loop(worker_id="worker-1"))
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.exception(f"Worker crashed: {e}")
        sys.exit(1)
