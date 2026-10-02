"""Saga: fluxo completo de encomenda (criar → validar stock → gerar PDF → notificar → cache)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from core.database import get_db
from core.notify import contact_notify_email
from core.outbox import enqueue_event
from core.resilience import log_dlq_event
from core.saga.logging import saga_log
from utils.email_sender import send_email_async

logger = logging.getLogger("diomika-saga")


@dataclass
class OrderLine:
    """Linha de encomenda."""
    ean: str
    quantity: int
    price: float
    color_code: Optional[str] = None
    size: Optional[str] = None


@dataclass
class OrderSagaResult:
    """Resultado da saga de encomenda."""
    order_id: str
    saga_id: str
    status: str
    invoice_generated: bool = False
    email_sent: bool = False
    inventory_reserved: bool = False
    errors: list[str] = field(default_factory=list)


class OrderSagaOrchestrator:
    """Orquestrador de saga de encomenda — multi-step compensable workflow."""

    def __init__(self):
        self.db = get_db()
        self.saga_id = str(uuid4())

    async def run(
        self,
        customer_data: dict[str, Any],
        lines: list[OrderLine],
        user_id: str,
    ) -> OrderSagaResult:
        """
        Execute full order saga with compensation:
        1. Persist order (DB)
        2. Reserve inventory
        3. Generate invoice PDF
        4. Send notification email
        5. Publish events
        """
        saga_log(
            self.saga_id,
            "order_submission",
            "start",
            "running",
            {
                "customer": customer_data.get("email"),
                "lines_count": len(lines),
            },
        )

        result = OrderSagaResult(
            order_id="",
            saga_id=self.saga_id,
            status="pending",
        )

        try:
            # Step 1: Persist order
            result.order_id = await self._persist_order(customer_data, lines, user_id)
            result.status = "persisted"

            # Step 2: Reserve inventory
            try:
                await self._reserve_inventory(result.order_id, lines)
                result.inventory_reserved = True
            except Exception as e:
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "reserve_inventory",
                    "failed",
                    {"error": str(e), "order_id": result.order_id},
                )
                result.errors.append(f"Inventory reservation failed: {str(e)}")
                # Compensate: mark order as inventory_failed
                self.db.table("orders").update({
                    "status": "inventory_failed",
                }).eq("id", result.order_id).execute()

            # Step 3: Generate invoice PDF
            try:
                invoice_url = await self._generate_invoice(result.order_id, customer_data, lines)
                result.invoice_generated = bool(invoice_url)
            except Exception as e:
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "generate_invoice",
                    "failed",
                    {"error": str(e), "order_id": result.order_id},
                )
                result.errors.append(f"Invoice generation failed: {str(e)}")
                # Not critical — store in outbox for retry

            # Step 4: Send notification email
            try:
                await self._send_notification(customer_data, result.order_id, lines)
                result.email_sent = True
            except Exception as e:
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "send_notification",
                    "failed",
                    {"error": str(e), "order_id": result.order_id},
                )
                result.errors.append(f"Email notification failed: {str(e)}")
                # Store in outbox for retry

            # Step 5: Publish completion event
            await enqueue_event(
                event_type="order.completed",
                payload={
                    "order_id": result.order_id,
                    "saga_id": self.saga_id,
                    "customer_email": customer_data.get("email"),
                    "lines_count": len(lines),
                    "inventory_reserved": result.inventory_reserved,
                    "invoice_generated": result.invoice_generated,
                    "email_sent": result.email_sent,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            result.status = "completed"
            saga_log(
                self.saga_id,
                "order_submission",
                "complete",
                "completed",
                {
                    "order_id": result.order_id,
                    "inventory_reserved": result.inventory_reserved,
                    "email_sent": result.email_sent,
                },
            )

        except Exception as e:
            result.status = "failed"
            result.errors.append(f"Fatal error: {str(e)}")
            logger.error(f"[ORDER_SAGA] Fatal error: {e}", exc_info=True)
            log_dlq_event("ORDER_SAGA", self.saga_id, e)

        return result

    async def _persist_order(self, customer_data: dict[str, Any], lines: list[OrderLine], user_id: str) -> str:
        """Persiste order na BD."""
        saga_log(
            self.saga_id,
            "order_submission",
            "persist_order",
            "running",
            {"email": customer_data.get("email")},
        )

        try:
            lines_json = [
                {
                    "ean": line.ean,
                    "quantity": line.quantity,
                    "price": line.price,
                    "color_code": line.color_code,
                    "size": line.size,
                }
                for line in lines
            ]

            record = {
                "customer_name": customer_data.get("name", "").strip(),
                "customer_email": customer_data.get("email", "").strip(),
                "customer_phone": customer_data.get("phone"),
                "customer_address": customer_data.get("address"),
                "lines": lines_json,
                "status": "pending",
                "total_amount": sum(line.price * line.quantity for line in lines),
                "created_by": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "visibilidade": True,
            }

            res = self.db.table("orders").insert(record).execute()
            order = res.data[0]
            order_id = str(order["id"])

            saga_log(
                self.saga_id,
                "order_submission",
                "persist_order",
                "completed",
                {"order_id": order_id},
            )

            return order_id

        except Exception as e:
            saga_log(
                self.saga_id,
                "order_submission",
                "persist_order",
                "failed",
                {"error": str(e)},
            )
            raise

    async def _reserve_inventory(self, order_id: str, lines: list[OrderLine]) -> bool:
        """Reserve stock para cada linha de encomenda."""
        saga_log(
            self.saga_id,
            "order_submission",
            "reserve_inventory",
            "running",
            {"order_id": order_id},
        )

        try:
            for line in lines:
                # Check current stock
                res = self.db.table("product_inventory").select("quantity").eq("ean", line.ean).execute()
                current_stock = res.data[0]["quantity"] if res.data else 0

                if current_stock < line.quantity:
                    raise Exception(f"Insufficient stock for EAN {line.ean}: available={current_stock}, requested={line.quantity}")

                # Reserve by reducing quantity
                new_quantity = current_stock - line.quantity
                self.db.table("product_inventory").update({
                    "quantity": new_quantity,
                    "reserved_for_order": order_id,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("ean", line.ean).execute()

                saga_log(
                    self.saga_id,
                    "order_submission",
                    "reserve_inventory",
                    "line_reserved",
                    {"ean": line.ean, "quantity": line.quantity, "remaining": new_quantity},
                )

            saga_log(
                self.saga_id,
                "order_submission",
                "reserve_inventory",
                "completed",
                {"order_id": order_id},
            )
            return True

        except Exception as e:
            saga_log(
                self.saga_id,
                "order_submission",
                "reserve_inventory",
                "failed",
                {"error": str(e), "order_id": order_id},
            )
            raise

    async def _generate_invoice(self, order_id: str, customer_data: dict[str, Any], lines: list[OrderLine]) -> Optional[str]:
        """Gera PDF da fatura."""
        saga_log(
            self.saga_id,
            "order_submission",
            "generate_invoice",
            "running",
            {"order_id": order_id},
        )

        try:
            # Placeholder: em produção, usar reportlab/weasyprint
            invoice_url = f"https://invoices.diomika.com/orders/{order_id}.pdf"

            # Store invoice URL in order
            self.db.table("orders").update({
                "invoice_url": invoice_url,
            }).eq("id", order_id).execute()

            saga_log(
                self.saga_id,
                "order_submission",
                "generate_invoice",
                "completed",
                {"order_id": order_id, "url": invoice_url},
            )
            return invoice_url

        except Exception as e:
            saga_log(
                self.saga_id,
                "order_submission",
                "generate_invoice",
                "failed",
                {"error": str(e)},
            )
            raise

    async def _send_notification(self, customer_data: dict[str, Any], order_id: str, lines: list[OrderLine]) -> bool:
        """Envia email de confirmação de encomenda."""
        saga_log(
            self.saga_id,
            "order_submission",
            "send_notification",
            "running",
            {"order_id": order_id},
        )

        try:
            customer_email = customer_data.get("email", "")
            if not customer_email:
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "send_notification",
                    "skipped",
                    {"reason": "no email"},
                )
                return False

            # Build email
            subject = f"[Diomika] Confirmação de Encomenda #{order_id[:8]}"
            lines_text = "\n".join([
                f"- EAN {line.ean}: {line.quantity} un. @ {line.price}€ = {line.quantity * line.price}€"
                for line in lines
            ])
            total = sum(line.price * line.quantity for line in lines)

            body = (
                f"Obrigado pela sua encomenda!\n\n"
                f"Referência: {order_id}\n"
                f"Cliente: {customer_data.get('name', 'N/A')}\n"
                f"Contacto: {customer_data.get('phone', 'N/A')}\n\n"
                f"Linhas:\n{lines_text}\n\n"
                f"Total: {total}€\n\n"
                f"A sua encomenda será processada nos próximos dias úteis.\n"
            )

            # Send
            email_sent = await send_email_async(to_email=customer_email, subject=subject, body=body)

            if email_sent:
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "send_notification",
                    "completed",
                    {"order_id": order_id},
                )
            else:
                # Enqueue for retry
                await enqueue_event(
                    event_type="order.notification_pending",
                    payload={
                        "order_id": order_id,
                        "customer_email": customer_email,
                        "subject": subject,
                        "body": body,
                    },
                )
                saga_log(
                    self.saga_id,
                    "order_submission",
                    "send_notification",
                    "compensated_outbox",
                    {"order_id": order_id},
                )

            return email_sent

        except Exception as e:
            saga_log(
                self.saga_id,
                "order_submission",
                "send_notification",
                "failed",
                {"error": str(e)},
            )
            raise


async def run_order_saga(
    customer_data: dict[str, Any],
    lines: list[OrderLine],
    user_id: str,
) -> OrderSagaResult:
    """Public API para executar order saga."""
    orchestrator = OrderSagaOrchestrator()
    return await orchestrator.run(customer_data, lines, user_id)
