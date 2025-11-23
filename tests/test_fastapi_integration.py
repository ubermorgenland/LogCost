import logging

import pytest

_fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import logcost


def test_fastapi_logging_tracked():
    logcost.reset()
    app = FastAPI()
    logger = logging.getLogger("logcost.fastapi")
    logger.setLevel(logging.INFO)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int):
        logger.info("FastAPI item %s", item_id)
        return {"item": item_id}

    with TestClient(app) as client:
        response = client.get("/items/123")
        assert response.status_code == 200

    stats = logcost.get_stats()
    matches = [
        entry for entry in stats.values()
        if entry["message_template"] == "FastAPI item %s"
    ]
    assert matches, "FastAPI log entry not recorded"
    entry = matches[0]
    assert entry["file"].endswith("tests/test_fastapi_integration.py")
    assert entry["count"] == 1
    logcost.reset()
