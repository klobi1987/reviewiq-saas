"""
ReviewIQ Local Development Starter
==================================
Runs both web server and worker for local testing.
"""

import subprocess
import sys
import time
import signal
from pathlib import Path

def main():
    """Start web server and worker in parallel."""
    print("=" * 60)
    print("  ReviewIQ Local Development")
    print("  Web: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 60)
    print()

    # Start web server
    web_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=Path(__file__).parent
    )

    # Give web server time to start
    time.sleep(2)

    # Start worker
    worker_process = subprocess.Popen(
        [sys.executable, "task_queue.py"],
        cwd=Path(__file__).parent
    )

    print("\n[STARTUP] Web server and worker are running")
    print("[STARTUP] Press Ctrl+C to stop both\n")

    def shutdown(signum, frame):
        print("\n[SHUTDOWN] Stopping services...")
        web_process.terminate()
        worker_process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for processes
    try:
        web_process.wait()
        worker_process.wait()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
