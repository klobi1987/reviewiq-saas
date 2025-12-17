"""
ReviewIQ SaaS Backend
=====================
FastAPI backend for handling Stripe payments and report delivery.

Endpoints:
- POST /create-checkout - Creates Stripe checkout session
- POST /webhook - Handles Stripe webhooks
- GET /report/{report_id} - Serves hosted reports
- GET /report/{report_id}/pdf - Downloads PDF version
"""

import os
import sys
import uuid
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import stripe

# Local imports only - no external path manipulation needed

from config import settings

# Initialize FastAPI
app = FastAPI(
    title="ReviewIQ API",
    description="Review Intelligence SaaS Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Database path
DB_PATH = Path(__file__).parent.parent / "database" / "orders.db"
REPORTS_PATH = Path(__file__).parent.parent / "reports"


# ============== Database ==============

def init_db():
    """Initialize SQLite database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            restaurant_url TEXT NOT NULL,
            restaurant_name TEXT,
            stripe_session_id TEXT,
            stripe_payment_intent TEXT,
            status TEXT DEFAULT 'pending',
            amount INTEGER,
            currency TEXT DEFAULT 'eur',
            report_id TEXT,
            report_url TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            order_id TEXT,
            restaurant_name TEXT,
            total_reviews INTEGER,
            countries_count INTEGER,
            avg_rating REAL,
            positive_pct REAL,
            html_path TEXT,
            pdf_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            view_count INTEGER DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    REPORTS_PATH.mkdir(parents=True, exist_ok=True)


# ============== Models ==============

class CheckoutRequest(BaseModel):
    email: EmailStr
    restaurant_url: str
    restaurant_name: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class OrderStatus(BaseModel):
    id: str
    status: str
    report_url: Optional[str]
    expires_at: Optional[str]


class ScrapeRequest(BaseModel):
    email: EmailStr
    restaurant_url: str
    restaurant_name: Optional[str] = None


class ScrapeResponse(BaseModel):
    order_id: str
    status: str
    message: str


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "status": "ok",
        "service": "ReviewIQ API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy"}


@app.post("/start-scrape", response_model=ScrapeResponse)
async def start_scrape(request: ScrapeRequest):
    """
    Start scraping without payment.

    Creates order and queues scraping task immediately.
    """
    try:
        # Generate unique order ID
        order_id = str(uuid.uuid4())[:8]
        restaurant_name = request.restaurant_name or "Restaurant"

        # Save order to database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (id, email, restaurant_url, restaurant_name, status)
            VALUES (?, ?, ?, ?, 'processing')
        """, (order_id, request.email, request.restaurant_url, restaurant_name))
        conn.commit()
        conn.close()

        # Queue scraping task for worker
        from task_queue import add_task, init_task_db
        init_task_db()

        task_id = add_task("scrape_and_report", {
            "order_id": order_id,
            "email": request.email,
            "restaurant_url": request.restaurant_url,
            "restaurant_name": restaurant_name
        })

        print(f"[API] Task {task_id} queued for order {order_id}")
        print(f"[API] URL: {request.restaurant_url}")

        return ScrapeResponse(
            order_id=order_id,
            status="queued",
            message=f"Scraping started! Task ID: {task_id}. Check /order/{order_id} for status."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(request: CheckoutRequest):
    """
    Create a Stripe Checkout session.

    Returns checkout URL for redirecting user to Stripe payment page.
    """
    try:
        # Generate unique order ID
        order_id = str(uuid.uuid4())[:8]

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": settings.STRIPE_PRICE_ID,  # Your product price ID
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/?canceled=true",
            customer_email=request.email,
            metadata={
                "order_id": order_id,
                "restaurant_url": request.restaurant_url,
                "restaurant_name": request.restaurant_name or "",
            },
            expires_at=int((datetime.now() + timedelta(hours=1)).timestamp()),
        )

        # Save order to database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (id, email, restaurant_url, restaurant_name, stripe_session_id, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (order_id, request.email, request.restaurant_url, request.restaurant_name, checkout_session.id))
        conn.commit()
        conn.close()

        return CheckoutResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Stripe webhook events.

    Processes payment confirmations and triggers report generation.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Update order status
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE orders
            SET status = 'paid',
                stripe_payment_intent = ?,
                amount = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE stripe_session_id = ?
        """, (
            session.get("payment_intent"),
            session.get("amount_total"),
            session["id"]
        ))

        # Get order details
        cursor.execute("SELECT * FROM orders WHERE stripe_session_id = ?", (session["id"],))
        order = cursor.fetchone()
        conn.commit()
        conn.close()

        if order:
            # Queue scraping task for worker to process
            from task_queue import add_task, init_task_db
            init_task_db()

            task_id = add_task("scrape_and_report", {
                "order_id": order["id"],
                "email": order["email"],
                "restaurant_url": order["restaurant_url"],
                "restaurant_name": order["restaurant_name"]
            })

            print(f"[WEBHOOK] Task {task_id} queued for order {order['id']}")

    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE orders SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE stripe_session_id = ?
        """, (session["id"],))
        conn.commit()
        conn.close()

    return {"status": "success"}


@app.get("/order/{order_id}", response_model=OrderStatus)
async def get_order_status(order_id: str):
    """Get order status and report URL if available."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderStatus(
        id=order["id"],
        status=order["status"],
        report_url=order["report_url"],
        expires_at=order["expires_at"]
    )


@app.get("/r/{report_id}", response_class=HTMLResponse)
async def view_report(report_id: str):
    """
    Serve the hosted report page.

    This is the public URL sent to customers.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check expiration
    if report["expires_at"]:
        expires = datetime.fromisoformat(report["expires_at"])
        if datetime.now() > expires:
            conn.close()
            raise HTTPException(status_code=410, detail="Report has expired")

    # Increment view count
    cursor.execute("""
        UPDATE reports SET view_count = view_count + 1 WHERE id = ?
    """, (report_id,))
    conn.commit()
    conn.close()

    # Read and return HTML
    html_path = Path(report["html_path"])
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/r/{report_id}/pdf")
async def download_report_pdf(report_id: str):
    """Download PDF version of the report."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    conn.close()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check expiration
    if report["expires_at"]:
        expires = datetime.fromisoformat(report["expires_at"])
        if datetime.now() > expires:
            raise HTTPException(status_code=410, detail="Report has expired")

    pdf_path = Path(report["pdf_path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"ReviewIQ_{report['restaurant_name']}.pdf"
    )


# ============== Background Tasks ==============

async def process_order(order_id: str, email: str, restaurant_url: str, restaurant_name: str):
    """
    Process a paid order:
    1. Scrape reviews (or queue for manual processing)
    2. Generate report
    3. Generate PDF
    4. Send email to customer
    """
    from report_service import generate_report_for_order
    from email_service import send_report_email

    try:
        # Generate report
        report_id = await generate_report_for_order(
            order_id=order_id,
            restaurant_url=restaurant_url,
            restaurant_name=restaurant_name
        )

        # Update order with report info
        report_url = f"{settings.BASE_URL}/r/{report_id}"
        expires_at = (datetime.now() + timedelta(days=90)).isoformat()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE orders
            SET status = 'completed', report_id = ?, report_url = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (report_id, report_url, expires_at, order_id))
        conn.commit()
        conn.close()

        # Send email
        await send_report_email(
            to_email=email,
            report_url=report_url,
            pdf_url=f"{settings.BASE_URL}/r/{report_id}/pdf",
            restaurant_name=restaurant_name
        )

    except Exception as e:
        # Log error and update status
        print(f"Error processing order {order_id}: {e}")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE orders SET status = 'error', updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (order_id,))
        conn.commit()
        conn.close()


# ============== Admin Endpoints ==============

@app.get("/admin/orders")
async def list_orders(status: Optional[str] = None, api_key: str = None):
    """List all orders (admin only)."""
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cursor = conn.cursor()

    if status:
        cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")

    orders = cursor.fetchall()
    conn.close()

    return [dict(order) for order in orders]


@app.post("/admin/generate-report/{order_id}")
async def admin_generate_report(order_id: str, background_tasks: BackgroundTasks, api_key: str = None):
    """Manually trigger report generation for an order (admin only)."""
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    background_tasks.add_task(
        process_order,
        order_id=order["id"],
        email=order["email"],
        restaurant_url=order["restaurant_url"],
        restaurant_name=order["restaurant_name"]
    )

    return {"status": "queued", "order_id": order_id}


# ============== Run Server ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
