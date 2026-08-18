"""Preuve locale de séparation réseau public/private avec un Nginx réel.

Le test utilise deux listeners distincts : loopback public et interface privée
eth0. Il ne remplace pas la validation du firewall et du TLS du VPS client.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests

API = "http://127.0.0.1:8000"
PRIVATE_IP = os.environ.get("PRIVATE_TEST_IP", "169.254.0.21")
CONTAINER = "autocommerce_network_boundary_nginx"
PUBLIC_PORT = "18080"
PRIVATE_PORT = "18081"
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@clinic.local")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, capture_output=True, timeout=20)


def main() -> int:
    if not ADMIN_PASSWORD:
        raise RuntimeError("E2E_ADMIN_PASSWORD requis hors dépôt")
    config = f"""
server {{
    listen 0.0.0.0:{PUBLIC_PORT};
    server_name public.test;
    location ^~ /api/public/ {{ proxy_pass http://127.0.0.1:8000; }}
    location ^~ /api/private/ {{ return 404; }}
    location ^~ /api/v1/ {{ return 404; }}
    location / {{ return 404; }}
}}
server {{
    listen {PRIVATE_IP}:{PRIVATE_PORT};
    server_name private.test;
    location ^~ /api/private/ {{ proxy_pass http://127.0.0.1:8000; }}
    location ^~ /api/public/ {{ return 404; }}
    location / {{ return 404; }}
}}
"""
    config_path = Path(tempfile.mkstemp(prefix="autocommerce-nginx-boundary-", suffix=".conf")[1])
    config_path.write_text(config, encoding="utf-8")
    try:
        run(["sudo", "docker", "rm", "-f", CONTAINER], check=False)
        run(
            [
                "sudo", "docker", "run", "-d", "--name", CONTAINER,
                "--network", "host", "-v", f"{config_path}:/etc/nginx/conf.d/default.conf:ro",
                "nginx:alpine",
            ]
        )
        for _ in range(20):
            try:
                if requests.get(f"http://127.0.0.1:{PUBLIC_PORT}/api/public/actes", timeout=1).status_code:
                    break
            except requests.RequestException:
                time.sleep(0.5)

        public = requests.get(f"http://127.0.0.1:{PUBLIC_PORT}/api/public/actes", timeout=10)
        assert public.status_code == 200, f"public gateway={public.status_code} {public.text[:200]}"

        public_private = requests.get(
            f"http://127.0.0.1:{PUBLIC_PORT}/api/private/auth/me", timeout=10
        )
        assert public_private.status_code == 404, f"public private exposure={public_private.status_code}"
    except requests.RequestException as exc:
        raise AssertionError(f"public gateway unavailable: {exc}") from exc

    try:
        requests.get(f"http://127.0.0.1:{PRIVATE_PORT}/api/private/auth/me", timeout=5)
    except requests.RequestException:
        loopback_status = "BLOCKED"
    else:
        raise AssertionError("private listener must not be reachable from public loopback")

    try:
        login = requests.post(
            f"{API}/api/private/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert login.status_code == 200, f"direct login={login.status_code}"
        access_token = login.json()["access_token"]
        private = requests.get(
            f"http://{PRIVATE_IP}:{PRIVATE_PORT}/api/private/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        assert private.status_code == 200, f"private authenticated={private.status_code} {private.text[:200]}"
        print(
            "NETWORK BOUNDARY PASS: public_gateway=200 public_to_private=404 "
            f"public_private_listener={loopback_status} private_authenticated=200 ({PRIVATE_IP})"
        )
        return 0
    finally:
        run(["sudo", "docker", "rm", "-f", CONTAINER], check=False)
        config_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
