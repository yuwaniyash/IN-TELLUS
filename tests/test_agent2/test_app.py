import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from Agents.agent2_calc.app import app
from Security_Layer.auth import get_current_company_id
import Agents.agent2_calc.app as app_module

# Override auth for testing — real JWT decoding is Security_Layer's own
# concern and already covered by their tests; here we only need to
# confirm Agent 2's route wiring behaves correctly given a company_id.
app.dependency_overrides[get_current_company_id] = lambda: 42

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["agent"] == "Agent 2"


def test_analyze_rejects_invalid_file_id_at_pydantic_layer():
    # Pydantic's Field(gt=0) catches this before our own validator runs —
    # that's FastAPI's standard 422, not our validator's 400.
    response = client.post("/analyze", json={"file_id": -1})
    assert response.status_code == 422


def test_analyze_rejects_dangerous_sector_via_our_own_validator():
    # This is what security_validation.py exists to catch — Pydantic's
    # type system alone wouldn't flag a dangerous string content.
    response = client.post("/analyze", json={"file_id": 1, "sector": "<script>alert(1)</script>"})
    assert response.status_code == 400
    assert "errors" in response.json()["detail"]


def test_analyze_rejects_invalid_region():
    response = client.post("/analyze", json={"file_id": 1, "region": "mars"})
    assert response.status_code == 400


def test_analyze_returns_404_when_orchestrator_reports_file_not_found():
    with patch.object(app_module, "run_full_analysis", return_value={"errors": ["file not found"], "result": None}):
        response = client.post("/analyze", json={"file_id": 999})
    assert response.status_code == 404


def test_analyze_success_path_returns_result_and_updates_status():
    fake_result = {
        "file_id": 1, "resource_type": "electricity",
        "footprint": {"company_total": {"total_kg": 123.4}}, "site_reports": [],
    }
    with patch.object(app_module, "run_full_analysis", return_value={"errors": [], "result": fake_result}), \
         patch.object(app_module, "update_processing_status") as mock_status_update:
        response = client.post("/analyze", json={"file_id": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["result"]["file_id"] == 1
    mock_status_update.assert_called_once_with(1, "ANALYZED")


def test_analyze_succeeds_even_if_status_update_fails():
    """A failed 'mark as analyzed' write should never take down an otherwise-successful analysis."""
    fake_result = {"file_id": 1, "resource_type": "electricity", "footprint": {}, "site_reports": []}
    with patch.object(app_module, "run_full_analysis", return_value={"errors": [], "result": fake_result}), \
         patch.object(app_module, "update_processing_status", side_effect=RuntimeError("db hiccup")):
        response = client.post("/analyze", json={"file_id": 1})
    assert response.status_code == 200
    assert response.json()["success"] is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
