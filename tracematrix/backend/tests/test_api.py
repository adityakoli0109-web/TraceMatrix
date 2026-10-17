from app.services.jobs import run_job


def test_health_and_auth(client, auth_headers):
    assert client.get("/health").json()["status"] == "ok"
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "analyst@example.com"
    denied = client.get("/api/v1/auth/me")
    assert denied.status_code == 401
    bad = client.post("/api/v1/auth/login", json={"email": "analyst@example.com", "password": "wrong-password"})
    assert bad.status_code == 401


def test_investigation_fixture_pipeline(client, auth_headers):
    preview = client.post(
        "/api/v1/investigations",
        headers=auth_headers,
        json={
            "title": "Fixture case",
            "description": "Known graph",
            "seed_value": "0x1111111111111111111111111111111111111111",
            "objective": "Validate scoring",
            "max_depth": 2,
            "max_transactions": 20,
            "confirm_scope": False,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["confirmation_required"] is True

    created = client.post(
        "/api/v1/investigations",
        headers=auth_headers,
        json={
            "title": "Fixture case",
            "description": "Known graph",
            "seed_value": "0x1111111111111111111111111111111111111111",
            "objective": "Validate scoring",
            "max_depth": 2,
            "max_transactions": 20,
            "confirm_scope": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    inv_id = body["investigation"]["id"]
    job_id = body["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert job["status"] in {"success", "failed"}
    if job["status"] != "success":
        raise AssertionError(job)

    dashboard = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert dashboard["totals"]["investigations"] >= 1
    assert dashboard["empty"] is False

    txs = client.get(f"/api/v1/investigations/{inv_id}/transactions", headers=auth_headers).json()
    assert txs["total"] == 2

    graph = client.get(f"/api/v1/investigations/{inv_id}/graph", headers=auth_headers).json()
    assert len(graph["nodes"]) == 3
    assert graph["notice"]

    lookup = client.get(
        "/api/v1/explorer/lookup",
        headers=auth_headers,
        params={"q": "0x1111111111111111111111111111111111111111"},
    ).json()
    assert lookup["status"] == "ok"
    assert lookup["result"]["is_fixture"] is True

    evidence = client.get(f"/api/v1/investigations/{inv_id}/evidence", headers=auth_headers).json()
    assert evidence["items"]
    candidates = client.get(f"/api/v1/investigations/{inv_id}/candidates", headers=auth_headers).json()
    assert candidates["items"]
    lead = next(c for c in candidates["items"] if c["wallet_address"].startswith("0x3333"))
    assert lead["label"] in {"direct_indicator_match", "investigative_lead", "unverified_attribution"}
    review = client.post(
        f"/api/v1/candidates/{lead['id']}/review",
        headers=auth_headers,
        json={"decision": "under_review", "rationale": "Needs independent corroboration."},
    )
    assert review.status_code == 200

    report = client.post(f"/api/v1/investigations/{inv_id}/reports/json", headers=auth_headers)
    assert report.status_code == 200
    assert "executive_summary" in report.json()["body"]

    invalid = client.post(
        "/api/v1/investigations",
        headers=auth_headers,
        json={"title": "bad", "seed_value": "not-an-address", "confirm_scope": True},
    )
    assert invalid.status_code == 400
