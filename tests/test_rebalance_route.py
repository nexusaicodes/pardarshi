import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # No need for lifespan — /rebalance doesn't use the pipeline
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_payload():
    return json.dumps({
        "portfolio": {
            "portfolio_value_raw": 10000.0,
            "cash_raw": 2000.0,
            "instruments_raw": {"AAA": 5000.0, "BBB": 3000.0},
        },
        "targets": {"AAA": 60, "BBB": 20},
    })


@pytest.fixture
def shortfall_payload():
    return json.dumps({
        "portfolio": {
            "portfolio_value_raw": 10000.0,
            "cash_raw": 2000.0,
            "instruments_raw": {"AAA": 5000.0, "BBB": 3000.0},
        },
        "targets": {"AAA": 90},
    })


class TestRebalanceRoute:
    def test_valid_rebalance_returns_200(self, client, valid_payload):
        resp = client.post("/rebalance", data={"payload": valid_payload})
        assert resp.status_code == 200

    def test_response_contains_action_tags(self, client, valid_payload):
        resp = client.post("/rebalance", data={"payload": valid_payload})
        html = resp.text
        assert "Buy" in html or "Sell" in html

    def test_response_contains_rebalanced_table(self, client, valid_payload):
        resp = client.post("/rebalance", data={"payload": valid_payload})
        assert "After Rebalance" in resp.text

    def test_shortfall_returns_error_html(self, client, shortfall_payload):
        resp = client.post("/rebalance", data={"payload": shortfall_payload})
        assert "Insufficient cash" in resp.text

    def test_malformed_json_returns_error(self, client):
        resp = client.post("/rebalance", data={"payload": "not-json"})
        assert resp.status_code >= 400 or "error" in resp.text.lower()

    def test_missing_fields(self, client):
        resp = client.post("/rebalance", data={"payload": json.dumps({"portfolio": {}})})
        assert resp.status_code >= 400 or "error" in resp.text.lower()
