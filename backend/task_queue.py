"""
ReviewIQ Task Queue
===================
Simple SQLite-based task queue for background scraping jobs.
No Redis needed - perfect for small scale.

For higher scale, switch to Redis + Celery.
"""

import sqlite3
import json
import time
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional
import sys

from config import settings


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def init_task_db():
    """Initialize task queue table."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            retries INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def add_task(task_type: str, payload: dict) -> int:
    """Add a new task to the queue."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (task_type, payload) VALUES (?, ?)",
        (task_type, json.dumps(payload))
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_pending_task() -> Optional[dict]:
    """Get the next pending task."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_type, payload, retries
        FROM tasks
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "task_type": row[1],
            "payload": json.loads(row[2]),
            "retries": row[3]
        }
    return None


def update_task_status(task_id: int, status: TaskStatus, result: str = None, error: str = None):
    """Update task status."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()

    if status == TaskStatus.PROCESSING:
        cursor.execute(
            "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
            (status.value, datetime.now().isoformat(), task_id)
        )
    elif status == TaskStatus.COMPLETED:
        cursor.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ? WHERE id = ?",
            (status.value, result, datetime.now().isoformat(), task_id)
        )
    elif status == TaskStatus.FAILED:
        cursor.execute(
            "UPDATE tasks SET status = ?, error = ?, completed_at = ?, retries = retries + 1 WHERE id = ?",
            (status.value, error, datetime.now().isoformat(), task_id)
        )

    conn.commit()
    conn.close()


async def process_scrape_task(payload: dict) -> str:
    """
    Process a scraping task.

    This runs the TripAdvisor scraper, generates report, and sends email.
    """
    order_id = payload["order_id"]
    restaurant_url = payload["restaurant_url"]
    restaurant_name = payload["restaurant_name"]
    customer_email = payload["email"]

    print(f"[WORKER] Starting scrape for order {order_id}")
    print(f"[WORKER] URL: {restaurant_url}")

    # Import scraper from scrapers folder
    scrapers_path = Path(__file__).parent.parent.parent / "scrapers"
    sys.path.insert(0, str(scrapers_path))

    try:
        # 1. Run the scraper
        from tripadvisor.scraper import TripAdvisorScraper

        # Create temp output folder
        output_dir = settings.REPORTS_PATH / order_id
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "reviews.csv"

        print(f"[WORKER] Scraping reviews...")

        # Run scraper in thread (it's synchronous with selenium)
        def run_scraper():
            scraper = TripAdvisorScraper(
                base_url=restaurant_url,
                max_reviews=500  # Limit for €49 tier
            )
            scraper.run()
            return scraper.reviews

        reviews = await asyncio.to_thread(run_scraper)

        # Save to CSV
        import pandas as pd
        df = pd.DataFrame(reviews)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"[WORKER] Scraped {len(reviews)} reviews")

        # 2. Generate report
        from report_service import generate_report_for_order, update_report_with_data

        # Check if report already exists (placeholder)
        conn = sqlite3.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM reports WHERE order_id = ?", (order_id,))
        existing = cursor.fetchone()
        conn.close()

        if existing:
            # Update existing placeholder report
            report_id = existing[0]
            await update_report_with_data(report_id, str(csv_path), restaurant_name)
        else:
            # Generate new report
            report_id = await generate_report_for_order(
                order_id=order_id,
                restaurant_url=restaurant_url,
                restaurant_name=restaurant_name,
                csv_path=str(csv_path)
            )

        print(f"[WORKER] Report generated: {report_id}")

        # 3. Send email
        from email_service import send_report_email

        report_url = f"{settings.BASE_URL}/r/{report_id}"
        pdf_url = f"{settings.BASE_URL}/r/{report_id}/pdf"

        await send_report_email(
            to_email=customer_email,
            report_url=report_url,
            pdf_url=pdf_url,
            restaurant_name=restaurant_name
        )

        print(f"[WORKER] Email sent to {customer_email}")

        # 4. Update order status
        conn = sqlite3.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = 'completed', report_id = ? WHERE id = ?",
            (report_id, order_id)
        )
        conn.commit()
        conn.close()

        return f"Success: {report_id}"

    except Exception as e:
        print(f"[WORKER] Error: {str(e)}")
        traceback.print_exc()
        raise


async def run_worker():
    """
    Main worker loop - polls for tasks and processes them.

    Run this as a separate process:
    python task_queue.py
    """
    print("[WORKER] Starting ReviewIQ worker...")
    init_task_db()

    while True:
        task = get_pending_task()

        if task:
            task_id = task["id"]
            task_type = task["task_type"]
            payload = task["payload"]

            print(f"[WORKER] Processing task {task_id}: {task_type}")
            update_task_status(task_id, TaskStatus.PROCESSING)

            try:
                if task_type == "scrape_and_report":
                    result = await process_scrape_task(payload)
                    update_task_status(task_id, TaskStatus.COMPLETED, result=result)
                    print(f"[WORKER] Task {task_id} completed")
                else:
                    raise ValueError(f"Unknown task type: {task_type}")

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                update_task_status(task_id, TaskStatus.FAILED, error=error_msg)
                print(f"[WORKER] Task {task_id} failed: {error_msg}")

                # Retry logic (max 3 retries)
                if task["retries"] < 3:
                    conn = sqlite3.connect(settings.DATABASE_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE tasks SET status = 'pending' WHERE id = ?",
                        (task_id,)
                    )
                    conn.commit()
                    conn.close()
                    print(f"[WORKER] Task {task_id} queued for retry")

        else:
            # No tasks, wait before polling again
            await asyncio.sleep(5)


# Run worker directly
if __name__ == "__main__":
    asyncio.run(run_worker())
