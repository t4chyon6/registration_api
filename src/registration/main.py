"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from registration import config
from registration.api import exception_handlers
from registration.api.routes import users
from registration.infrastructure import database, email


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources for the FastAPI application."""
    settings = config.get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    async with AsyncExitStack() as stack:
        pool = await stack.enter_async_context(database.lifespan_pool(settings))
        email_service = await stack.enter_async_context(email.EmailService(settings))

        app.state.settings = settings
        app.state.pool = pool
        app.state.email_service = email_service

        yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = config.get_settings()
    app = FastAPI(
        title="Registration API",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.include_router(users.router)
    exception_handlers.register_exception_handlers(app)
    return app


app = create_app()
