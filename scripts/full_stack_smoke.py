"""Smoke test full-stack de la surface privée avec données synthétiques."""
from __future__ import annotations

import os
import sys
import time

import requests

API = "http://127.0.0.1:8000"
PRIVATE = f"{API}/api/private"
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@clinic.local")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD")


def check(response: requests.Response, expected: int, label: str) -> requests.Response:
    if response.status_code != expected:
        raise AssertionError(f"{label}: HTTP {response.status_code}, {response.text[:300]}")
    return response


def main() -> int:
    if not ADMIN_PASSWORD:
        raise AssertionError("E2E_ADMIN_PASSWORD requis hors dépôt")
    session = requests.Session()
    login = check(
        session.post(
            f"{PRIVATE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10,
        ),
        200,
        "login",
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    check(session.get(f"{PRIVATE}/auth/me", headers=headers, timeout=10), 200, "auth/me")
    check(session.get(f"{PRIVATE}/auth/mfa/status", headers=headers, timeout=10), 200, "MFA status")

    patients = check(session.get(f"{PRIVATE}/patients", headers=headers, timeout=10), 200, "patients")
    rows = patients.json()
    patient_id = rows[0]["id"] if rows else 1
    check(session.get(f"{PRIVATE}/patients/{patient_id}/dossiers", headers=headers, timeout=10), 200, "dossiers")
    check(session.get(f"{PRIVATE}/agenda", headers=headers, timeout=10), 200, "agenda")
    check(session.get(f"{PRIVATE}/factures", headers=headers, timeout=10), 200, "factures")
    lot_payload = {
        "produit_id": 1,
        "numero_lot": "FULL-STACK-" + str(time.time_ns())[-10:],
        "date_expiration": "2030-12-31",
        "quantite_initiale": 5,
        "quantite_restante": 5,
        "fournisseur": "synthetic-test",
        "prix_achat_lot": 1,
    }
    check(session.post(f"{PRIVATE}/injectables/lots", json=lot_payload, headers=headers, timeout=10), 200, "stock lot creation")
    check(session.get(f"{PRIVATE}/injectables/stock", headers=headers, timeout=10), 200, "stock overview")
    capabilities = check(
        session.get(f"{PRIVATE}/assistant-ia/capabilities", headers=headers, timeout=10),
        200,
        "IA capabilities",
    )
    if not capabilities.json().get("tools"):
        raise AssertionError("IA capabilities sans tools")

    check(session.post(f"{PRIVATE}/auth/logout", headers=headers, timeout=10), 204, "logout")
    print("FULL STACK PASS: login mfa patients dossiers agenda facturation stock ia logout")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, requests.RequestException) as exc:
        print(f"FULL STACK FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
