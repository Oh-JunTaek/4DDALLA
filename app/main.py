"""4 DDALLA bootstrap — FastAPI application (P1-01A).

This ticket only establishes the minimal application and the shared contract
foundation (ENUMs, envelope skeleton) plus health/contract tests. No scraping,
no map/place API integration, no OCR/LLM connection, no automatic publication.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="4 DDALLA API",
    version="0.1.0",
    description="Bootstrap baseline. Only /health is implemented at this stage.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the bootstrap baseline."""
    return {"status": "ok"}
