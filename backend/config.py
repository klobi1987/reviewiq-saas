"""
ReviewIQ Configuration
======================
All configuration settings for the SaaS platform.

Environment variables should be set in production.
For local development, you can create a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if exists
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


class Settings:
    """Application settings."""

    # App
    APP_NAME: str = "ReviewIQ"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # URLs
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_xxx")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "price_xxx")  # Your product price ID

    # Email (Resend - simpler than SendGrid)
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "re_xxx")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "ReviewIQ <info@reviewiq.hr>")

    # Admin
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "change-this-in-production")

    # Paths
    REPORTS_PATH: Path = Path(__file__).parent.parent / "reports"
    DATABASE_PATH: Path = Path(__file__).parent.parent / "database" / "orders.db"

    # Report settings
    REPORT_EXPIRY_DAYS: int = 90  # 3 months

    # Pricing
    PRICE_EUR: int = 49  # Price in EUR


settings = Settings()


# ============== Stripe Product Setup Instructions ==============
"""
TO SET UP STRIPE:

1. Create Stripe account: https://stripe.com
2. Go to Dashboard > Products
3. Create new product:
   - Name: "ReviewIQ Analysis"
   - Description: "AI-powered review analysis with country breakdown"
   - Price: €49.00 (one-time)
4. Copy the Price ID (starts with "price_")
5. Go to Developers > Webhooks
6. Add endpoint: https://yourdomain.com/webhook
7. Select events: checkout.session.completed, checkout.session.expired
8. Copy Webhook Secret (starts with "whsec_")
9. Add keys to .env file

STRIPE TEST CARDS:
- Success: 4242 4242 4242 4242
- Decline: 4000 0000 0000 0002
- 3D Secure: 4000 0027 6000 3184
"""


# ============== Resend Email Setup Instructions ==============
"""
TO SET UP RESEND (easier than SendGrid):

1. Create account: https://resend.com
2. Verify your domain (or use their test domain)
3. Go to API Keys > Create API Key
4. Copy API key to .env file

Free tier: 3,000 emails/month - plenty for starting!
"""
