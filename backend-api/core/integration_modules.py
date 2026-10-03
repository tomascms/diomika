"""
Integração de módulos profissionais no FastAPI.

Este ficheiro centraliza a inicialização de:
- CQRS handlers
- WebSocket manager
- API versioning middleware
- Event subscribers
- Saga orchestrators
"""
import asyncio
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse

from core.api_versioning_middleware import APIVersionMiddleware
from core.cqrs_admin_handlers import (
    CreateEntityHandler,
    UpdateEntityHandler,
    DeleteEntityHandler,
    CreateEntityCommand,
    UpdateEntityCommand,
    DeleteEntityCommand,
)
from core.event_subscribers import EventSubscriptionManager, EventSubscriber
from core.websocket_backoffice import get_ws_manager, BackofficeWSManager, start_ws_heartbeat
from core.auth import require_ops
from core.local_only import admin_must_be_local

logger = logging.getLogger("diomika-integration")


class ProfessionalModulesIntegrator:
    """Orquestrador de inicialização dos módulos profissionais."""

    def __init__(self):
        self.cqrs_handlers = {}
        self.event_manager: Optional[EventSubscriptionManager] = None
        self.ws_manager: Optional[BackofficeWSManager] = None

    def setup_cqrs_handlers(self) -> dict:
        """Initialize CQRS handlers."""
        self.cqrs_handlers = {
            "create": CreateEntityHandler(),
            "update": UpdateEntityHandler(),
            "delete": DeleteEntityHandler(),
        }
        logger.info("[CQRS] Handlers initialized: %s", list(self.cqrs_handlers.keys()))
        return self.cqrs_handlers

    def setup_event_subscribers(self) -> EventSubscriptionManager:
        """Initialize event subscription manager."""
        self.event_manager = EventSubscriptionManager()

        # Register built-in subscribers
        # Em produção, seria feito com dependency injection
        logger.info("[Events] Subscription manager initialized")
        return self.event_manager

    def setup_websocket(self) -> BackofficeWSManager:
        """Initialize WebSocket manager."""
        self.ws_manager = get_ws_manager()
        logger.info("[WebSocket] Manager initialized")
        return self.ws_manager

    async def startup(self):
        """Run startup tasks."""
        logger.info("[Integration] Starting up professional modules...")

        # Initialize CQRS
        self.setup_cqrs_handlers()

        # Initialize Event Subscribers
        self.setup_event_subscribers()

        # Initialize WebSocket
        self.setup_websocket()

        # Start WebSocket heartbeat
        await start_ws_heartbeat()

        logger.info("[Integration] All modules started successfully")

    async def shutdown(self):
        """Run shutdown tasks."""
        logger.info("[Integration] Shutting down professional modules...")
        # Cleanup tasks would go here
        logger.info("[Integration] Shutdown complete")


# Global integrator instance
_integrator: Optional[ProfessionalModulesIntegrator] = None


def get_integrator() -> ProfessionalModulesIntegrator:
    """Get global integrator."""
    global _integrator
    if _integrator is None:
        _integrator = ProfessionalModulesIntegrator()
    return _integrator


def integrate_professional_modules(app: FastAPI) -> ProfessionalModulesIntegrator:
    """
    Integrate all professional modules into FastAPI app.

    This should be called early in app setup, after middleware but before routes.
    """
    integrator = get_integrator()

    # Add middleware for API versioning
    app.add_middleware(APIVersionMiddleware)

    # Startup and shutdown events
    @app.on_event("startup")
    async def on_startup():
        await integrator.startup()

    @app.on_event("shutdown")
    async def on_shutdown():
        await integrator.shutdown()

    # WebSocket endpoint for backoffice real-time updates
    @app.websocket("/ws/backoffice")
    async def websocket_backoffice_endpoint(
        websocket: WebSocket,
        user_id: str = "",
        token: str = "",
    ):
        """
        WebSocket endpoint para backoffice.

        Client connects with query params:
        - user_id: Backoffice user ID
        - token: Authentication token
        """
        # TODO: Validate token
        if not user_id:
            await websocket.close(code=4000, reason="Missing user_id")
            return

        ws_manager = integrator.ws_manager
        if not ws_manager:
            await websocket.close(code=5000, reason="WebSocket unavailable")
            return

        client_id = f"{user_id}-{asyncio.current_task()}"

        try:
            await ws_manager.connect(websocket, user_id, client_id)

            # Receive messages loop
            while True:
                data = await websocket.receive_text()
                # Process incoming message (subscribe, heartbeat, etc)
                logger.debug(f"[WS] Message from {user_id}: {data}")

        except WebSocketDisconnect:
            await ws_manager.disconnect(user_id, client_id)
            logger.info(f"[WS] Client disconnected: {user_id}")
        except Exception as e:
            logger.error(f"[WS] Error: {e}", exc_info=True)
            try:
                await websocket.close(code=1011, reason=str(e))
            except:
                pass

    # Health check endpoint (WebSocket related)
    @app.get("/health/websocket")
    async def health_websocket(user_id: str = Depends(require_ops)):
        """Check WebSocket manager health."""
        ws_manager = integrator.ws_manager
        if not ws_manager:
            return JSONResponse({"status": "unhealthy", "component": "websocket"}, status_code=503)

        return {
            "status": "healthy",
            "component": "websocket",
            "active_connections": len(ws_manager.active_connections),
            "subscriptions": {k: len(v) for k, v in ws_manager.subscriptions.items()},
        }

    logger.info("[Integration] Professional modules integrated into FastAPI app")
    return integrator


# Helper functions para acesso aos módulos

def get_cqrs_handlers() -> dict:
    """Get registered CQRS handlers."""
    integrator = get_integrator()
    return integrator.cqrs_handlers


def get_event_manager() -> Optional[EventSubscriptionManager]:
    """Get event subscription manager."""
    integrator = get_integrator()
    return integrator.event_manager


def get_ws_backoffice() -> Optional[BackofficeWSManager]:
    """Get WebSocket manager."""
    integrator = get_integrator()
    return integrator.ws_manager
