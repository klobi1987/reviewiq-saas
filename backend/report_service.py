"""
ReviewIQ Report Service
=======================
Generates HTML and PDF reports from scraped review data.
"""

import sys
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from config import settings

# Import the report generator from scrapers
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scrapers" / "analysis"))


async def generate_report_for_order(
    order_id: str,
    restaurant_url: str,
    restaurant_name: str,
    csv_path: str = None
) -> str:
    """
    Generate a report for an order.

    In production, this would:
    1. Run the scraper on restaurant_url
    2. Generate the HTML report
    3. Generate PDF version
    4. Save to database

    For now, we'll generate from existing CSV or create a placeholder.

    Args:
        order_id: Unique order ID
        restaurant_url: URL of the restaurant on TripAdvisor/Google
        restaurant_name: Name of the restaurant
        csv_path: Optional path to already scraped CSV

    Returns:
        report_id: Unique report ID for accessing the report
    """
    from report_generator import generate_report, generate_html_template
    import pandas as pd

    # Generate unique report ID
    report_id = str(uuid.uuid4())[:12]

    # Create report directory
    report_dir = settings.REPORTS_PATH / report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    html_path = report_dir / "index.html"
    pdf_path = report_dir / "report.pdf"

    # If CSV provided, generate real report
    if csv_path and Path(csv_path).exists():
        # Use existing report generator
        generated_file = generate_report(csv_path, restaurant_name, str(report_dir))

        # Rename to index.html
        if generated_file and Path(generated_file).exists():
            Path(generated_file).rename(html_path)

        # Read CSV for stats
        df = pd.read_csv(csv_path)
        total_reviews = len(df)

        # Get country count
        if 'location' in df.columns or 'nationality' in df.columns:
            loc_col = 'location' if 'location' in df.columns else 'nationality'
            countries_count = df[loc_col].nunique()
        else:
            countries_count = 0

        # Get avg rating
        for col in ['rating', 'overall_rating', 'stars']:
            if col in df.columns:
                avg_rating = df[col].mean()
                break
        else:
            avg_rating = 0

        positive_pct = 85.0  # Placeholder - would come from sentiment analysis

    else:
        # Generate placeholder/demo report
        # In production, this would trigger the scraper first
        html_content = generate_placeholder_report(restaurant_name, restaurant_url, report_id)
        html_path.write_text(html_content, encoding="utf-8")

        total_reviews = 0
        countries_count = 0
        avg_rating = 0
        positive_pct = 0

    # Generate PDF from HTML
    await generate_pdf(html_path, pdf_path)

    # Save to database
    expires_at = (datetime.now() + timedelta(days=settings.REPORT_EXPIRY_DAYS)).isoformat()

    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (id, order_id, restaurant_name, total_reviews, countries_count, avg_rating, positive_pct, html_path, pdf_path, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_id, order_id, restaurant_name, total_reviews, countries_count,
        avg_rating, positive_pct, str(html_path), str(pdf_path), expires_at
    ))
    conn.commit()
    conn.close()

    return report_id


async def generate_pdf(html_path: Path, pdf_path: Path):
    """
    Generate PDF from HTML report.

    Uses playwright for high-quality PDF generation.
    Falls back to weasyprint if playwright not available.
    """
    try:
        # Try playwright first (best quality)
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Load HTML file
            await page.goto(f"file://{html_path.absolute()}")

            # Generate PDF
            await page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={
                    "top": "20px",
                    "bottom": "20px",
                    "left": "20px",
                    "right": "20px"
                }
            )

            await browser.close()
            return True

    except ImportError:
        print("Playwright not installed, trying weasyprint...")

    try:
        # Fallback to weasyprint
        from weasyprint import HTML

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True

    except ImportError:
        print("WeasyPrint not installed, PDF generation skipped")

    # If no PDF library available, create placeholder
    pdf_path.write_text("PDF generation requires playwright or weasyprint")
    return False


def generate_placeholder_report(restaurant_name: str, restaurant_url: str, report_id: str) -> str:
    """
    Generate a placeholder report when scraping hasn't been done yet.

    This is shown when admin needs to manually run the scraper.
    """
    return f'''<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReviewIQ Report | {restaurant_name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .container {{
            text-align: center;
            max-width: 600px;
        }}
        .badge {{
            display: inline-block;
            background: linear-gradient(135deg, #f59e0b, #f97316);
            color: #000;
            padding: 0.75rem 2rem;
            border-radius: 50px;
            font-weight: 700;
            font-size: 0.85rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 2rem;
        }}
        h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 1rem;
        }}
        .restaurant {{
            font-size: 1.5rem;
            color: #a78bfa;
            margin-bottom: 2rem;
        }}
        .message {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
        }}
        .message h2 {{
            color: #10b981;
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
        }}
        .message p {{
            color: rgba(255,255,255,0.7);
        }}
        .spinner {{
            width: 60px;
            height: 60px;
            border: 4px solid rgba(99, 102, 241, 0.3);
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 2rem auto;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .info {{
            color: rgba(255,255,255,0.5);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">ReviewIQ Report</div>
        <h1>Izvještaj u pripremi</h1>
        <p class="restaurant">{restaurant_name}</p>

        <div class="message">
            <h2>Vaša narudžba je zaprimljena!</h2>
            <p>Naš tim trenutno analizira recenzije za vaš restoran. Izvještaj će biti spreman uskoro.</p>
        </div>

        <div class="spinner"></div>

        <p class="info">
            Report ID: {report_id}<br>
            Primiti ćete email kada izvještaj bude spreman.
        </p>
    </div>

    <script>
        // Auto-refresh every 30 seconds to check if report is ready
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
'''


async def update_report_with_data(report_id: str, csv_path: str, restaurant_name: str):
    """
    Update an existing placeholder report with real data.

    Call this after scraping is complete to replace the placeholder.
    """
    from report_generator import generate_report
    import pandas as pd

    # Get existing report path
    report_dir = settings.REPORTS_PATH / report_id
    html_path = report_dir / "index.html"
    pdf_path = report_dir / "report.pdf"

    # Generate new report
    generated_file = generate_report(csv_path, restaurant_name, str(report_dir))

    if generated_file and Path(generated_file).exists():
        # Rename to index.html
        Path(generated_file).rename(html_path)

    # Regenerate PDF
    await generate_pdf(html_path, pdf_path)

    # Update database with stats
    df = pd.read_csv(csv_path)
    total_reviews = len(df)

    if 'location' in df.columns or 'nationality' in df.columns:
        loc_col = 'location' if 'location' in df.columns else 'nationality'
        countries_count = df[loc_col].nunique()
    else:
        countries_count = 0

    for col in ['rating', 'overall_rating', 'stars']:
        if col in df.columns:
            avg_rating = df[col].mean()
            break
    else:
        avg_rating = 0

    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE reports
        SET total_reviews = ?, countries_count = ?, avg_rating = ?
        WHERE id = ?
    """, (total_reviews, countries_count, avg_rating, report_id))
    conn.commit()
    conn.close()

    return True
