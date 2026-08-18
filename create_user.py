"""Créer un utilisateur initial à partir de variables d'environnement uniquement.

Ce script est destiné à l'amorçage contrôlé d'une installation. Aucun secret,
email ou mot de passe par défaut n'est embarqué dans le dépôt.
"""

import os

from passlib.context import CryptContext
from sqlalchemy import create_engine, text


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Variable obligatoire absente: {name}")
    return value


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
database_url = required("DATABASE_URL")
admin_email = required("ADMIN_EMAIL")
admin_password = required("ADMIN_PASSWORD")
clinic_id = int(os.environ.get("CLINIC_ID", "1"))

engine = create_engine(database_url)
with engine.begin() as conn:
    conn.execute(
        text(
            """
            INSERT INTO utilisateurs (
                email, nom, prenom, hashed_password, role, clinic_id,
                created_at, updated_at, taux_commission, is_active,
                mfa_enabled, mfa_failed_attempts
            )
            VALUES (
                :email, :nom, :prenom, :pwd, :role, :clinic_id,
                NOW(), NOW(), :commission, true, false, 0
            )
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {
            "email": admin_email,
            "nom": os.environ.get("ADMIN_LAST_NAME", "Admin"),
            "prenom": os.environ.get("ADMIN_FIRST_NAME", "Initial"),
            "pwd": pwd_context.hash(admin_password),
            "role": "admin",
            "clinic_id": clinic_id,
            "commission": 0.0,
        },
    )

print("Utilisateur initial créé ou déjà présent.")
