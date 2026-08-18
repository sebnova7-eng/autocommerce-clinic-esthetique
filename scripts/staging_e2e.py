"""Validation HTTP staging réelle avec données synthétiques uniquement."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import requests

API_ORIGIN = "http://127.0.0.1:8000"
PRIVATE = f"{API_ORIGIN}/api/private"
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@clinic.local")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD")
CLINIC_B_EMAIL = os.environ.get("E2E_CLINIC_B_EMAIL", "admin@clinic-b.local")
CLINIC_B_PASSWORD = os.environ.get("E2E_CLINIC_B_PASSWORD")
PUBLIC = f"{API_ORIGIN}/api/public"


def fail(message: str) -> None:
    raise AssertionError(message)


def assert_status(response: requests.Response, expected: int | tuple[int, ...], label: str) -> None:
    expected_values = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_values:
        fail(f"{label}: HTTP {response.status_code}, body={response.text[:500]}")


def cookie_value(response: requests.Response, name: str = "autocommerce_refresh") -> str:
    jar = response.cookies.get(name)
    if jar:
        return jar
    parsed = SimpleCookie()
    parsed.load(response.headers.get("set-cookie", ""))
    if name not in parsed:
        fail(f"cookie {name} absent")
    return parsed[name].value


def login(email: str, password: str) -> tuple[requests.Session, str, str]:
    session = requests.Session()
    response = session.post(
        f"{PRIVATE}/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert_status(response, 200, f"login {email}")
    body = response.json()
    if "refresh_token" in body:
        fail("refresh_token présent dans le JSON de login")
    if "HttpOnly" not in response.headers.get("set-cookie", ""):
        fail("refresh cookie non HttpOnly")
    token = body["access_token"]
    old_refresh = cookie_value(response)
    return session, token, old_refresh


def main() -> int:
    # La surface privée refuse toute requête sans access token.
    anonymous = requests.Session()
    assert_status(anonymous.get(f"{PRIVATE}/patients", timeout=10), 401, "private sans auth")

    if not ADMIN_PASSWORD or not CLINIC_B_PASSWORD:
        fail("E2E_ADMIN_PASSWORD et E2E_CLINIC_B_PASSWORD requis hors dépôt")
    admin, access_token, old_refresh = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {access_token}"}
    assert_status(admin.get(f"{PRIVATE}/auth/me", headers=headers, timeout=10), 200, "auth/me")

    # Rotation du refresh cookie et absence de refresh token dans le JSON.
    rotated = admin.post(f"{PRIVATE}/auth/refresh", timeout=10)
    assert_status(rotated, 200, "refresh cookie")
    if "refresh_token" in rotated.json():
        fail("refresh_token présent dans le JSON de refresh")
    new_refresh = cookie_value(rotated)
    if new_refresh == old_refresh:
        fail("la rotation n’a pas remplacé le refresh cookie")

    replay = requests.Session()
    replay.cookies.set("autocommerce_refresh", old_refresh, path="/api/private/auth")
    replay_response = replay.post(f"{PRIVATE}/auth/refresh", timeout=10)
    assert_status(replay_response, 401, "reuse detection")

    # La Public Gateway est consultable sans token et ne renvoie pas de données médicales.
    public_praticiens = anonymous.get(f"{PUBLIC}/praticiens", timeout=10)
    assert_status(public_praticiens, 200, "public praticiens")
    public_actes = anonymous.get(f"{PUBLIC}/actes", timeout=10)
    assert_status(public_actes, 200, "public actes")
    acte_id = public_actes.json()[0]["id"]
    praticien_id = public_praticiens.json()[0]["id"]

    # Prochain jour ouvré à 10h pour un booking synthétique.
    nonce = str(time.time_ns())[-8:]
    requested = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30, minutes=int(nonce[-4:]))
    booking_payload = {
        "nom": "Demande",
        "prenom": "Publique",
        "telephone": "+2162" + nonce,
        "email": "booking.synthetic@example.com",
        "praticien_id": praticien_id,
        "acte_id": acte_id,
        "date_heure": requested.isoformat(),
        "clinic_id": 2,
    }
    booking = anonymous.post(f"{PUBLIC}/reservation", json=booking_payload, timeout=10)
    assert_status(booking, 202, "public booking request")
    booking_id = booking.json()["booking_request_id"]
    if booking.json()["statut"] != "pending":
        fail("BookingRequest publique non pending")

    duplicate = anonymous.post(f"{PUBLIC}/reservation", json=booking_payload, timeout=10)
    assert_status(duplicate, 202, "booking duplicate")
    if not duplicate.json().get("duplicate") or duplicate.json()["booking_request_id"] != booking_id:
        fail("déduplication BookingRequest absente")

    # La surface publique ne permet ni modification, ni annulation, ni enumeration.
    public_modify = anonymous.patch(f"{PUBLIC}/reservation/{booking_id}", json={"nom": "tampered"}, timeout=10)
    assert_status(public_modify, (404, 405), "public booking modification blocked")
    public_cancel = anonymous.delete(f"{PUBLIC}/reservation/{booking_id}", timeout=10)
    assert_status(public_cancel, (404, 405), "public booking cancellation blocked")
    public_enumeration = anonymous.get(f"{PUBLIC}/booking-requests/{booking_id}", timeout=10)
    assert_status(public_enumeration, (404, 405), "public booking enumeration blocked")

    # Contenu injecté : il est accepté comme donnée de demande mais jamais reflété.
    injection_payload = dict(booking_payload)
    injection_payload["nom"] = "<script>alert('x')</script>"
    injection_payload["telephone"] = "+2162" + str(time.time_ns())[-8:]
    injection = anonymous.post(f"{PUBLIC}/reservation", json=injection_payload, timeout=10)
    assert_status(injection, 202, "booking untrusted input")
    if "<script>" in injection.text.lower():
        fail("contenu injecté reflété par la Public Gateway")
    injection_booking_id = injection.json()["booking_request_id"]

    pending = admin.get(f"{PRIVATE}/booking-requests", params={"statut": "pending"}, headers=headers, timeout=10)
    assert_status(pending, 200, "list booking requests")
    if not any(row["id"] == booking_id for row in pending.json()):
        fail("BookingRequest invisible au Private Core")

    rejected = admin.post(
        f"{PRIVATE}/booking-requests/{injection_booking_id}/reject",
        json={"notes": "Demande de recette rejetée"},
        headers=headers,
        timeout=10,
    )
    assert_status(rejected, 200, "private booking rejection")
    if rejected.json().get("statut") != "rejected":
        fail("annulation interne BookingRequest absente")

    approved = admin.post(f"{PRIVATE}/booking-requests/{booking_id}/approve", headers=headers, timeout=10)
    assert_status(approved, 200, "approve booking request")
    if approved.json().get("statut") != "accepted" or not approved.json().get("rendez_vous_id"):
        fail("validation BookingRequest n’a pas créé le rendez-vous interne")

    # Clinic A ne peut pas lire la ressource synthétique de Clinic B.
    cross_tenant = admin.get(f"{PRIVATE}/patients/2", headers=headers, timeout=10)
    assert_status(cross_tenant, (403, 404), "cross-tenant patient access")
    list_with_client_tenant = admin.get(
        f"{PRIVATE}/patients", params={"clinic_id": 2}, headers=headers, timeout=10
    )
    assert_status(list_with_client_tenant, 200, "client clinic_id ignored")
    if any(row.get("email") == "patient-b@example.com" for row in list_with_client_tenant.json()):
        fail("patient Clinic B divulgué via clinic_id client")

    clinic_b, clinic_b_token, _ = login(CLINIC_B_EMAIL, CLINIC_B_PASSWORD)
    clinic_b_patient = clinic_b.get(
        f"{PRIVATE}/patients/2",
        headers={"Authorization": f"Bearer {clinic_b_token}"},
        timeout=10,
    )
    assert_status(clinic_b_patient, 200, "Clinic B own patient")

    # Logout révoque le cookie courant.
    logout = admin.post(f"{PRIVATE}/auth/logout", headers=headers, timeout=10)
    assert_status(logout, 204, "logout")
    after_logout = admin.post(f"{PRIVATE}/auth/refresh", timeout=10)
    assert_status(after_logout, 401, "refresh après logout")

    print("E2E PASS: auth-cookie rotation reuse public-gateway booking-request approval tenant-isolation logout")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, requests.RequestException) as exc:
        print(f"E2E FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
