"""
ReviewIQ Email Service
======================
Sends beautiful HTML emails to customers with report links.
Uses Resend API (simpler than SendGrid, great free tier).
"""

import httpx
from config import settings


async def send_report_email(
    to_email: str,
    report_url: str,
    pdf_url: str,
    restaurant_name: str
):
    """
    Send report delivery email to customer.

    Args:
        to_email: Customer's email address
        report_url: URL to web version of report
        pdf_url: URL to download PDF
        restaurant_name: Name of the analyzed restaurant
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border-radius: 20px; overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px; text-align: center;">
                                <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #fff;">
                                    Review<span style="color: #10b981;">IQ</span>
                                </h1>
                            </td>
                        </tr>

                        <!-- Main Content -->
                        <tr>
                            <td style="padding: 20px 40px;">
                                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 30px;">
                                    <p style="margin: 0; color: #10b981; font-size: 16px; font-weight: 600;">
                                        Vaš izvještaj je spreman!
                                    </p>
                                </div>

                                <p style="color: rgba(255,255,255,0.9); font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                                    Poštovani,
                                </p>

                                <p style="color: rgba(255,255,255,0.8); font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                                    Vaša AI analiza recenzija za <strong style="color: #fff;">{restaurant_name}</strong> je završena.
                                    U izvještaju ćete pronaći:
                                </p>

                                <ul style="color: rgba(255,255,255,0.8); font-size: 15px; line-height: 2; margin-bottom: 30px; padding-left: 20px;">
                                    <li>Detaljnu analizu po zemljama porijekla gostiju</li>
                                    <li>Sentiment analizu svih recenzija</li>
                                    <li>Ključne uvide i preporuke za poboljšanje</li>
                                    <li>Vizualni prikaz ocjena po tržištima</li>
                                </ul>

                                <!-- CTA Buttons -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                                    <tr>
                                        <td align="center" style="padding: 10px;">
                                            <a href="{report_url}" style="display: inline-block; background: linear-gradient(135deg, #6366f1, #ec4899); color: #fff; padding: 16px 40px; border-radius: 50px; text-decoration: none; font-weight: 700; font-size: 16px;">
                                                Pogledaj izvještaj
                                            </a>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center" style="padding: 10px;">
                                            <a href="{pdf_url}" style="display: inline-block; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 12px 30px; border-radius: 50px; text-decoration: none; font-weight: 600; font-size: 14px;">
                                                Preuzmi PDF verziju
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Expiry Notice -->
                                <div style="background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.2); border-radius: 8px; padding: 15px; text-align: center; margin: 30px 0;">
                                    <p style="margin: 0; color: #fbbf24; font-size: 13px;">
                                        Link vrijedi 3 mjeseca. Preporučamo preuzimanje PDF verzije.
                                    </p>
                                </div>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px 40px; border-top: 1px solid rgba(255,255,255,0.1); text-align: center;">
                                <p style="margin: 0 0 10px; color: rgba(255,255,255,0.5); font-size: 13px;">
                                    Imate pitanja? Javite nam se na info@reviewiq.hr
                                </p>
                                <p style="margin: 0; color: rgba(255,255,255,0.3); font-size: 12px;">
                                    ReviewIQ - AI-Powered Review Intelligence
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Plain text version
    text_content = f"""
    ReviewIQ - Vaš izvještaj je spreman!

    Poštovani,

    Vaša AI analiza recenzija za {restaurant_name} je završena.

    Pogledaj izvještaj: {report_url}
    Preuzmi PDF: {pdf_url}

    Link vrijedi 3 mjeseca.

    --
    ReviewIQ - AI-Powered Review Intelligence
    info@reviewiq.hr
    """

    # Send via Resend API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": f"Vaš ReviewIQ izvještaj za {restaurant_name} je spreman!",
                "html": html_content,
                "text": text_content
            }
        )

        if response.status_code != 200:
            print(f"Email error: {response.text}")
            raise Exception(f"Failed to send email: {response.text}")

        return response.json()


async def send_admin_notification(order_id: str, email: str, restaurant_url: str):
    """Send notification to admin when new order is placed."""

    html_content = f"""
    <h2>Nova narudžba!</h2>
    <p><strong>Order ID:</strong> {order_id}</p>
    <p><strong>Email:</strong> {email}</p>
    <p><strong>Restaurant URL:</strong> {restaurant_url}</p>
    <p>Potrebno je pokrenuti scraping i generirati izvještaj.</p>
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": settings.EMAIL_FROM,
                "to": ["admin@reviewiq.hr"],  # Your admin email
                "subject": f"Nova ReviewIQ narudžba - {order_id}",
                "html": html_content
            }
        )

        return response.json()
