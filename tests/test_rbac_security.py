"""
Module 10: Role-Based Access Control (RBAC) & Security Enforcement Tests.
Verifies JWT authentication, role restrictions (DHO vs Analyst vs Hospital Staff),
enforcement of 401 Unauthorized without token, and 403 Forbidden for non-DHO alert reviews.
"""

import pytest

def test_unauthenticated_request_rejected(client):
    # Alert acknowledgment requires authentication
    resp = client.post("/api/alerts/1/acknowledge", json={"review_notes": "test"})
    assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

def test_login_all_three_personas(client):
    personas = [
        ("dho_kp", "dho123", "district_health_officer"),
        ("analyst_kp", "analyst123", "data_analyst"),
        ("staff_ath", "staff123", "hospital_staff")
    ]
    for username, pwd, role in personas:
        resp = client.post("/api/auth/login", json={"username": username, "password": pwd})
        assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
        data = resp.json()
        assert data["role"] == role
        assert "access_token" in data

def test_dho_alert_acknowledgment_allowed(client, dho_headers, db_session):
    from backend.models.alert import Alert
    # Create an isolated temporary alert for this test so persistent alerts remain intact
    temp_alert = Alert(
        district_pcode="PK501",
        disease="Malaria",
        year=2026,
        epi_week=30,
        alert_level="watch",
        composite_score=0.5,
        ears_c1_score=2.1,
        ears_c2_score=2.0,
        ears_c3_score=1.8,
        forecast_breach=False,
        incidence_per_100k=20.0,
        headline="Temporary Test Alert",
        details="Automated test fixture",
        acknowledged=False
    )
    db_session.add(temp_alert)
    db_session.commit()
    db_session.refresh(temp_alert)

    try:
        resp = client.post(
            f"/api/alerts/{temp_alert.id}/acknowledge",
            json={"review_notes": "DHO formal verification confirmed in automated test."},
            headers=dho_headers
        )
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"].lower() == "acknowledged"
        assert res_data["acknowledged_by"] == "dho_kp"
    finally:
        db_session.delete(temp_alert)
        db_session.commit()

def test_non_dho_alert_acknowledgment_forbidden(client, analyst_headers, staff_headers):
    # Data Analyst cannot acknowledge DHO alerts (403 Forbidden)
    r1 = client.post(
        "/api/alerts/1/acknowledge",
        json={"review_notes": "Attempt by analyst"},
        headers=analyst_headers
    )
    assert r1.status_code == 403, f"Expected 403 for analyst, got {r1.status_code}"

    # Hospital Staff cannot acknowledge DHO alerts (403 Forbidden)
    r2 = client.post(
        "/api/alerts/1/acknowledge",
        json={"review_notes": "Attempt by staff"},
        headers=staff_headers
    )
    assert r2.status_code == 403, f"Expected 403 for hospital staff, got {r2.status_code}"
