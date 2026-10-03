"""Email HTML templates for order confirmations, notifications, and alerts.

Provides template rendering for:
- Order confirmation emails
- Payment confirmation
- Shipping notification
- Refund notification
- Password reset
- 2FA verification
- Alert notifications
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional


def render_order_confirmation(
    order_id: str,
    customer_name: str,
    order_date: datetime,
    items: list[dict],
    subtotal: Decimal,
    tax: Decimal,
    shipping: Decimal,
    total: Decimal,
    shipping_address: str,
    tracking_url: Optional[str] = None,
) -> str:
    """Render order confirmation email."""
    items_html = "\n".join(
        f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left;">
                {item['description']}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                {item['quantity']}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                ${float(item['unit_price']):.2f}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                ${float(item['quantity'] * item['unit_price']):.2f}
            </td>
        </tr>
        """
        for item in items
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; color: #1f2937; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
            .section {{ margin-bottom: 30px; }}
            .section-title {{ font-size: 14px; font-weight: 600; color: #374151; text-transform: uppercase; margin-bottom: 15px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #f3f4f6; padding: 12px; text-align: left; font-weight: 600; font-size: 12px; text-transform: uppercase; color: #6b7280; }}
            td {{ padding: 12px; }}
            .price-table {{ margin-top: 20px; width: 100%; }}
            .price-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .price-label {{ font-weight: 500; }}
            .price-value {{ text-align: right; }}
            .total-row {{ background: #dbeafe; padding: 15px; border-radius: 4px; font-size: 18px; font-weight: 700; color: #1e40af; display: flex; justify-content: space-between; }}
            .button {{ display: inline-block; background: #2563eb; color: white; padding: 12px 24px; border-radius: 4px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .button:hover {{ background: #1e40af; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
            .badge {{ display: inline-block; background: #d1fae5; color: #065f46; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✓ Order Confirmed</h1>
            </div>

            <div class="content">
                <p>Hi {customer_name},</p>

                <p>Thank you for your order! We've received your purchase and are preparing it for shipment.</p>

                <div class="section">
                    <div class="section-title">Order Details</div>
                    <div class="price-row">
                        <span class="price-label">Order Number:</span>
                        <span class="price-value"><strong>#{order_id}</strong></span>
                    </div>
                    <div class="price-row">
                        <span class="price-label">Order Date:</span>
                        <span class="price-value">{order_date.strftime('%B %d, %Y')}</span>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Items</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Description</th>
                                <th>Qty</th>
                                <th>Price</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>

                    <div class="price-table">
                        <div class="price-row">
                            <span class="price-label">Subtotal</span>
                            <span class="price-value">${float(subtotal):.2f}</span>
                        </div>
                        <div class="price-row">
                            <span class="price-label">Tax</span>
                            <span class="price-value">${float(tax):.2f}</span>
                        </div>
                        <div class="price-row">
                            <span class="price-label">Shipping</span>
                            <span class="price-value">${float(shipping):.2f}</span>
                        </div>
                        <div class="total-row">
                            <span>Total</span>
                            <span>${float(total):.2f}</span>
                        </div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Shipping Address</div>
                    <p style="margin: 0; white-space: pre-wrap;">{shipping_address}</p>
                </div>

                {f'''
                <div class="section">
                    <div class="section-title">Tracking</div>
                    <p>You can track your shipment here:</p>
                    <a href="{tracking_url}" class="button">Track Your Order</a>
                </div>
                ''' if tracking_url else ''}

                <p style="color: #6b7280; font-size: 14px;">
                    If you have any questions about your order, please contact our support team at support@diomika.com
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2024 Diomika. All rights reserved. | <a href="https://diomika.com" style="color: #2563eb; text-decoration: none;">diomika.com</a></p>
            </div>
        </div>
    </body>
    </html>
    """


def render_payment_confirmation(
    order_id: str,
    customer_name: str,
    amount: Decimal,
    payment_method: str,
    transaction_id: str,
) -> str:
    """Render payment confirmation email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; color: #1f2937; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
            .success-box {{ background: #d1fae5; border-left: 4px solid #10b981; padding: 20px; border-radius: 4px; margin-bottom: 20px; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .detail-label {{ font-weight: 500; color: #6b7280; }}
            .detail-value {{ font-weight: 600; color: #1f2937; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✓ Payment Confirmed</h1>
            </div>

            <div class="content">
                <p>Hi {customer_name},</p>

                <div class="success-box">
                    <strong style="color: #059669;">Your payment has been processed successfully!</strong>
                </div>

                <h3 style="margin-top: 0;">Payment Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Order Number</span>
                    <span class="detail-value">#{order_id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amount</span>
                    <span class="detail-value">${float(amount):.2f}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Payment Method</span>
                    <span class="detail-value">{payment_method}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Transaction ID</span>
                    <span class="detail-value">{transaction_id}</span>
                </div>

                <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">
                    For support, contact us at support@diomika.com
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2024 Diomika. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def render_shipping_notification(
    order_id: str,
    customer_name: str,
    carrier: str,
    tracking_number: str,
    tracking_url: str,
    estimated_delivery: Optional[str] = None,
) -> str:
    """Render shipping notification email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1f2937; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
            .tracking-box {{ background: #dbeafe; border: 2px solid #3b82f6; padding: 20px; border-radius: 4px; margin: 20px 0; text-align: center; }}
            .tracking-label {{ font-size: 12px; color: #1e40af; font-weight: 600; text-transform: uppercase; }}
            .tracking-number {{ font-size: 20px; font-weight: 700; color: #1e40af; margin: 10px 0; font-family: 'Courier New', monospace; }}
            .button {{ display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; border-radius: 4px; text-decoration: none; font-weight: 600; }}
            .button:hover {{ background: #1e40af; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📦 Your Order is On the Way!</h1>
            </div>

            <div class="content">
                <p>Hi {customer_name},</p>

                <p>Great news! Your order has been shipped and is on its way to you.</p>

                <h3>Shipment Details</h3>
                <div class="detail-row">
                    <span>Order Number</span>
                    <strong>#{order_id}</strong>
                </div>
                <div class="detail-row">
                    <span>Carrier</span>
                    <strong>{carrier}</strong>
                </div>
                {f'''
                <div class="detail-row">
                    <span>Estimated Delivery</span>
                    <strong>{estimated_delivery}</strong>
                </div>
                ''' if estimated_delivery else ''}

                <div class="tracking-box">
                    <div class="tracking-label">Tracking Number</div>
                    <div class="tracking-number">{tracking_number}</div>
                    <a href="{tracking_url}" class="button">Track Shipment</a>
                </div>

                <p style="color: #6b7280; font-size: 14px;">
                    You can track your shipment anytime by clicking the button above or visiting the carrier's website.
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2024 Diomika. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def render_refund_notification(
    order_id: str,
    customer_name: str,
    refund_amount: Decimal,
    reason: str,
    estimated_date: Optional[str] = None,
) -> str:
    """Render refund notification email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1f2937; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }}
            .refund-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 4px; margin-bottom: 20px; }}
            .amount {{ font-size: 28px; font-weight: 700; color: #d97706; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>↩️ Refund Initiated</h1>
            </div>

            <div class="content">
                <p>Hi {customer_name},</p>

                <p>We've processed your refund request and your money is on its way back to you.</p>

                <div class="refund-box">
                    <div style="font-size: 12px; color: #92400e; font-weight: 600;">Refund Amount</div>
                    <div class="amount">${float(refund_amount):.2f}</div>
                </div>

                <h3 style="margin-top: 20px;">Refund Details</h3>
                <div class="detail-row">
                    <span>Order Number</span>
                    <strong>#{order_id}</strong>
                </div>
                <div class="detail-row">
                    <span>Reason</span>
                    <strong>{reason}</strong>
                </div>
                {f'''
                <div class="detail-row">
                    <span>Expected in Account</span>
                    <strong>{estimated_date}</strong>
                </div>
                ''' if estimated_date else ''}

                <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">
                    Depending on your bank, refunds typically appear in 3-5 business days. If you don't see it after that time, please contact us.
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2024 Diomika. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def render_2fa_verification(customer_name: str, code: str, valid_for_minutes: int = 10) -> str:
    """Render 2FA verification code email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1f2937; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .content {{ background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; text-align: center; }}
            .code-box {{ background: #f3f4f6; border: 2px dashed #d1d5db; padding: 25px; border-radius: 8px; margin: 25px 0; }}
            .code {{ font-size: 32px; font-weight: 700; color: #8b5cf6; letter-spacing: 4px; font-family: 'Courier New', monospace; }}
            .warning {{ background: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; border-radius: 4px; margin: 20px 0; font-size: 14px; }}
            .footer {{ background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Verification Code</h1>
            </div>

            <div class="content">
                <p>Hi {customer_name},</p>

                <p>Your two-factor authentication code is:</p>

                <div class="code-box">
                    <div class="code">{code}</div>
                </div>

                <p style="color: #6b7280; margin: 20px 0;">
                    This code expires in <strong>{valid_for_minutes} minutes</strong>
                </p>

                <div class="warning">
                    <strong>⚠️ Security Notice:</strong> Never share this code with anyone. Diomika employees will never ask for this code.
                </div>

                <p style="color: #6b7280; font-size: 14px;">
                    If you didn't request this code, please secure your account immediately.
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2024 Diomika. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
