import ctypes
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

class ThreadManager:
    def __init__(self, cancellation_event):
        """Initialize ThreadManager with a cancellation event for signaling threads."""
        self.threads = []  # List of (thread, shutdown_obj) tuples
        self.cancellation_event = cancellation_event
        self.logger = logging.getLogger("ThreadManager")

    def add_thread(self, thread, shutdown_obj=None):
        """Add a thread and its optional shutdown object to the manager."""
        self.threads.append((thread, shutdown_obj))
        thread.start()
        self.logger.debug(f"Started thread: {thread.name}")

    def shutdown_all(self, timeout=5.0):
        """Shutdown all managed threads with a configurable timeout."""
        self.logger.info("Initiiating shutdown of all threads")
        self.cancellation_event.set()  # Signal all threads to stop

        # Call shutdown methods on associated objects if available
        for thread, shutdown_obj in self.threads:
            self.logger.error(f"Shutting down {thread.name}")

            if (
                shutdown_obj
                and hasattr(shutdown_obj, "shutdown")
                and callable(shutdown_obj.shutdown)
            ):
                try:
                    self.logger.debug(f"Calling shutdown on {shutdown_obj}")
                    shutdown_obj.shutdown()
                except Exception as e:
                    self.logger.error(f"Error shutting down {shutdown_obj}: {e}")

        # Join threads with the specified timeout
        for thread, _ in self.threads:
            if thread.is_alive():
                self.logger.debug(
                    f"Joining thread: {thread.name} with timeout {timeout}s"
                )
                thread.join(timeout=timeout)

        # Remove terminated threads from the list
        self.threads = [(t, s) for t, s in self.threads if t.is_alive()]

        if self.threads:
            self.logger.warning(
                f"{len(self.threads)} threads still alive: {[t.name for t, _ in self.threads]}"
            )
        else:
            self.logger.info("All threads terminated successfully")