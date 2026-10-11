import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from Agents.agent2_calc.app import app
from Security_Layer.auth import get_current_company_id
import Agents.agent2_calc.app as app_module
from Security_Layer import auth as auth_module

# Override auth for testing — real JWT decoding is Security_Layer's own
# concern; here we confirm Agent 2's route wiring behaves correctly given a
# company_id. The route also forwards the caller's bearer token to Agent 1
# and returns 401 if the Authorization header is missing, so the shared test
# client sends one. (Real JWT rejection is tested separately further down.)
app.dependency_overrides[get_current_company_id] = lambda: 42

client = TestClient(app, headers={"Authorization": "Bearer test-token"})


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


# ---- Authentication and tenant-isolation behaviour --------------------------

def test_analyze_requires_bearer_token_header():
    # company_id dependency is overridden, so this 401 comes from the route's
    # own check that a bearer token is present to forward to Agent 1.
    no_header_client = TestClient(app)
    response = no_header_client.post("/analyze", json={"file_id": 1})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_analyze_forwards_caller_token_to_agent1_link():
    fake_result = {"file_id": 1, "resource_type": "electricity", "footprint": {}, "site_reports": []}
    with patch.object(app_module, "run_full_analysis", return_value={"errors": [], "result": fake_result}) as run, \
         patch.object(app_module, "update_processing_status"):
        response = client.post("/analyze", json={"file_id": 1})
    assert response.status_code == 200
    kwargs = run.call_args.kwargs
    assert kwargs["auth_token"] == "test-token"
    assert kwargs["company_id"] == 42


@pytest.fixture
def real_auth():
    """Temporarily remove the company_id override so the real JWT check runs."""
    saved = app.dependency_overrides.pop(get_current_company_id)
    yield
    app.dependency_overrides[get_current_company_id] = saved


def test_real_auth_rejects_missing_invalid_and_expired_tokens(real_auth):
    plain = TestClient(app)
    expired = jwt.encode(
        {"sub": "1", "company_id": 42, "role": "member",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        auth_module.SECRET_KEY, algorithm=auth_module.ALGORITHM,
    )
    cases = {
        "no token": {},
        "tampered token": {"Authorization": "Bearer not.a.real-token"},
        "expired token": {"Authorization": f"Bearer {expired}"},
    }
    for label, headers in cases.items():
        response = plain.post("/analyze", json={"file_id": 1}, headers=headers)
        assert response.status_code == 401, label


def test_company_id_comes_from_token_not_request_body(real_auth):
    token = auth_module.create_access_token(user_id=7, company_id=42, role="member")
    fake_result = {"file_id": 1, "resource_type": "electricity", "footprint": {}, "site_reports": []}
    with patch.object(app_module, "run_full_analysis", return_value={"errors": [], "result": fake_result}) as run, \
         patch.object(app_module, "update_processing_status"):
        response = TestClient(app).post(
            "/analyze",
            json={"file_id": 1, "company_id": 999},   # a client claiming to be another company
            headers={"Authorization": f"Bearer {token}"},
        )
    # Either the extra field is ignored or the request is rejected; it must
    # never be used as the company scope.
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert run.call_args.kwargs["company_id"] == 42


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))