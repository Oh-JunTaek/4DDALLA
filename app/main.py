"""4 DDALLA bootstrap - FastAPI application (P1-01A).

This ticket only establishes the minimal application and the shared contract
foundation (ENUMs, envelope skeleton) plus health/contract tests. No scraping,
no map/place API integration, no OCR/LLM connection, no automatic publication.

P1-DB-02 adds database error mapping only: connection/unavailable and
configuration failures surface as safe JSON errors and never include connection
strings or credentials.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.db.dependencies import (
    database_configuration_handler,
    database_unavailable_handler,
)
from app.db.errors import DatabaseConfigurationError, DatabaseUnavailableError

app = FastAPI(
    title="4 DDALLA API",
    version="0.1.0",
    description="Bootstrap baseline. Only /health is implemented at this stage.",
)

app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
app.add_exception_handler(DatabaseConfigurationError, database_configuration_handler)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the bootstrap baseline."""
    return {"status": "ok"}
