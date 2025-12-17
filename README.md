# ReviewIQ SaaS Platform

A complete SaaS platform for selling AI-powered restaurant review analysis reports.

## Features

- **FULL AUTOMATION**: Customer pays → Scraper runs → Report generated → Email sent
- **Stripe Integration**: One-click checkout for €49 reports
- **Background Worker**: SQLite-based task queue (no Redis needed!)
- **Email Delivery**: Automated report delivery via Resend API
- **PDF Generation**: High-quality PDF reports using Playwright
- **Unique Report URLs**: Each report has a unique URL valid for 3 months
- **Mobile-Optimized**: Landing page and reports work perfectly on all devices

## Architecture

```
reviewiq-saas/
├── backend/
│   ├── main.py              # FastAPI application (web server)
│   ├── task_queue.py        # Background worker for scraping
│   ├── config.py            # Configuration & settings
│   ├── email_service.py     # Email sending (Resend API)
│   ├── report_service.py    # Report generation
│   ├── requirements.txt     # Python dependencies
│   ├── Procfile             # Railway deployment config
│   ├── railway.toml         # Railway settings
│   ├── start_local.py       # Local development runner
│   └── .env.example         # Environment template
├── frontend/
│   ├── index.html           # Landing page with order form
│   ├── success.html         # Post-payment success page
│   └── sample-report.html   # Sample report for preview
├── database/                # SQLite database (auto-created)
└── reports/                 # Generated reports storage
```

## Full Automation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CUSTOMER JOURNEY                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Customer visits landing page                                    │
│           ↓                                                         │
│  2. Enters email + TripAdvisor URL                                  │
│           ↓                                                         │
│  3. Clicks "Order" → Redirected to Stripe Checkout                  │
│           ↓                                                         │
│  4. Pays €49                                                        │
│           ↓                                                         │
│  5. Stripe sends webhook to /webhook                                │
│           ↓                                                         │
│  6. Backend adds task to SQLite queue                               │
│           ↓                                                         │
│  7. Worker picks up task, runs TripAdvisor scraper (5-30 min)       │
│           ↓                                                         │
│  8. Worker generates HTML report + PDF                              │
│           ↓                                                         │
│  9. Worker sends email with report links                            │
│           ↓                                                         │
│  10. Customer receives email, views report for 3 months             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Set Up Stripe

1. Create account at [stripe.com](https://stripe.com)
2. Go to **Products** → **Add product**
   - Name: "ReviewIQ Report"
   - Price: €49 EUR (one-time)
3. Copy the **Price ID** (starts with `price_`)
4. Go to **Developers** → **API Keys**
   - Copy **Publishable key** (starts with `pk_`)
   - Copy **Secret key** (starts with `sk_`)
5. Go to **Developers** → **Webhooks**
   - Add endpoint: `https://your-domain.com/webhook`
   - Select events: `checkout.session.completed`
   - Copy **Webhook secret** (starts with `whsec_`)

### 2. Set Up Resend (Email)

1. Create account at [resend.com](https://resend.com)
2. Add and verify your domain
3. Create API key and copy it

### 3. Configure Environment

```bash
cd reviewiq-saas/backend
cp .env.example .env
```

Edit `.env` with your values:
```
DEBUG=true
BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

STRIPE_SECRET_KEY=sk_test_xxxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxx
STRIPE_PRICE_ID=price_xxxx

RESEND_API_KEY=re_xxxx
EMAIL_FROM=ReviewIQ <info@reviewiq.hr>

ADMIN_API_KEY=your-secret-admin-key
```

### 4. Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Install playwright browsers for PDF generation
playwright install chromium
```

### 5. Run Backend (Web + Worker)

**Option A: Single command (recommended)**
```bash
cd backend
python start_local.py
```
This starts BOTH web server (port 8000) AND worker for task processing.

**Option B: Separate terminals**
```bash
# Terminal 1 - Web server
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 - Worker
cd backend
python task_queue.py
```

### 6. Serve Frontend

For development, use any static server:
```bash
cd frontend
python -m http.server 3000
```

For production, use Nginx or deploy to Netlify/Vercel.

### 7. Test Stripe Locally

Use Stripe CLI for webhook testing:
```bash
# Install Stripe CLI
# Windows: scoop install stripe
# Mac: brew install stripe/stripe-cli/stripe

# Forward webhooks to local
stripe listen --forward-to localhost:8000/webhook

# Copy the webhook signing secret and add to .env
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/create-checkout` | POST | Create Stripe checkout session |
| `/webhook` | POST | Handle Stripe webhooks |
| `/r/{report_id}` | GET | View report (HTML) |
| `/r/{report_id}/pdf` | GET | Download report (PDF) |
| `/admin/orders` | GET | List all orders (admin) |
| `/admin/reports/{report_id}/generate` | POST | Generate report (admin) |

## Workflow

1. **Customer** fills form on landing page
2. **Frontend** calls `/create-checkout` API
3. **Backend** creates Stripe session, stores order in DB
4. **Customer** redirected to Stripe Checkout
5. **Stripe** processes payment
6. **Stripe** sends webhook to `/webhook`
7. **Backend** marks order as paid, triggers report generation
8. **Admin** (or automation) runs scraper on restaurant URL
9. **Backend** generates HTML + PDF report
10. **Backend** sends email with report links
11. **Customer** views report at unique URL for 3 months

## Production Deployment

### Frontend → Netlify (FREE)

1. Go to [netlify.com](https://netlify.com) and login
2. Drag & drop `frontend/` folder to deploy
3. Or connect GitHub repo for auto-deploy
4. Update `API_BASE_URL` in `index.html` to your backend URL

### Backend → Railway (FREE tier available)

Railway runs BOTH web server AND worker process automatically!

1. Go to [railway.app](https://railway.app) and login
2. Create new project → Deploy from GitHub
3. Select your repository
4. Railway auto-detects `Procfile`:
   - `web`: FastAPI server (handles API calls)
   - `worker`: Task queue (runs scrapers)
5. Add environment variables in Railway dashboard:
   ```
   STRIPE_SECRET_KEY=sk_live_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_PRICE_ID=price_xxx
   RESEND_API_KEY=re_xxx
   BASE_URL=https://your-app.railway.app
   FRONTEND_URL=https://your-site.netlify.app
   ```
6. Update Stripe webhook URL to `https://your-app.railway.app/webhook`

### Alternative: Render (FREE)

1. Go to [render.com](https://render.com)
2. Create Web Service → Connect GitHub
3. Create Background Worker → Same repo, different start command
4. Web: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Worker: `python task_queue.py`

### Database

- SQLite works for starting (auto-created)
- For scale: Consider PostgreSQL (Railway/Render have free tiers)
- Add backup strategy for production

## Admin Tasks

### Manually Generate Report

```bash
curl -X POST "http://localhost:8000/admin/reports/ORDER_ID/generate" \
  -H "X-Admin-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/path/to/scraped/reviews.csv"}'
```

### View All Orders

```bash
curl "http://localhost:8000/admin/orders" \
  -H "X-Admin-Key: your-admin-key"
```

## License

Proprietary - ReviewIQ
