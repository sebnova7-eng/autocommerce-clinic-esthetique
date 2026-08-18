import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api-server"))

from bootstrap_admin import bootstrap
from config import get_settings

async def seed_admin_user(email: str, password: str) -> None:
    settings = get_settings()
    print(f"Attempting to bootstrap admin user: {email}")
    await bootstrap(
        email=email,
        nom="Admin",
        prenom="Clinic",
        password=password,
        role="DIRECTRICE",
        force=True,
    )

if __name__ == "__main__":
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        raise SystemExit("ADMIN_EMAIL et ADMIN_PASSWORD doivent être injectés hors dépôt; aucun défaut n’est autorisé.")
    if len(admin_password) < 20:
        raise SystemExit("ADMIN_PASSWORD doit contenir au moins 20 caractères.")
    asyncio.run(seed_admin_user(admin_email, admin_password))
