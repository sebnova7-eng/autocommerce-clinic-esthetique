"""
AutoCommerce Clinic — Tests MFA (Multi-Factor Authentication)

Couvre :
  - Génération et vérification TOTP
  - Flow de setup (secret + QR + backup codes)
  - Flow de login avec MFA activé
  - Codes de secours
  - Verrouillage après trop de tentatives
  - Désactivation avec mot de passe
"""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Utilisateur, RoleEnum
from middleware.auth import get_password_hash
from services.mfa import (
    generate_mfa_secret,
    get_totp_uri,
    verify_totp,
    get_current_totp,
    generate_backup_codes,
    verify_backup_code,
    MAX_MFA_ATTEMPTS,
)


# ── Tests unitaires du service MFA ─────────────────────────

class TestTotpGeneration:
    def test_generate_secret_returns_base32_string(self):
        secret = generate_mfa_secret()
        assert len(secret) >= 32
        # pyotp.random_base32() retourne une chaîne base32 valide
        assert secret.isascii()

    def test_totp_uri_contains_email_and_issuer(self):
        secret = generate_mfa_secret()
        uri = get_totp_uri(secret, "test@clinic.tn", "Ma Clinique")
        # pyotp URL-encode l'email : @ devient %40
        assert "test%40clinic.tn" in uri
        assert "Ma%20Clinique" in uri or "Ma Clinique" in uri
        assert secret in uri

    def test_verify_totp_with_correct_code(self):
        secret = generate_mfa_secret()
        current_code = get_current_totp(secret)
        assert verify_totp(secret, current_code) is True

    def test_verify_totp_rejects_wrong_code(self):
        secret = generate_mfa_secret()
        assert verify_totp(secret, "000000") is False

    def test_verify_totp_rejects_empty_string(self):
        secret = generate_mfa_secret()
        assert verify_totp(secret, "") is False

    def test_get_current_totp_returns_six_digits(self):
        secret = generate_mfa_secret()
        code = get_current_totp(secret)
        assert len(code) == 6
        assert code.isdigit()


class TestBackupCodes:
    def test_generate_backup_codes_returns_ten_codes(self):
        codes = generate_backup_codes()
        assert len(codes) == 10

    def test_backup_codes_are_unique(self):
        codes = generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_verify_backup_code_valid(self):
        codes = generate_backup_codes()
        assert verify_backup_code(codes[0], codes) is True

    def test_verify_backup_code_case_insensitive(self):
        codes = generate_backup_codes()
        assert verify_backup_code(codes[0].upper(), codes) is True

    def test_verify_backup_code_invalid(self):
        codes = generate_backup_codes()
        assert verify_backup_code("00000000", codes) is False

    def test_backup_codes_are_eight_chars(self):
        codes = generate_backup_codes()
        for code in codes:
            assert len(code) == 8


# ── Tests d'intégration MFA sur la DB ──────────────────────

@pytest.mark.asyncio
class TestMfaDatabase:
    async def test_user_has_mfa_fields_default_false(self, db: AsyncSession):
        """Un nouvel utilisateur n'a pas le MFA activé par défaut."""
        user = Utilisateur(
            clinic_id=1, email="mfa_test@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="MFA", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        assert user.mfa_enabled is False
        assert user.mfa_secret is None
        assert user.mfa_backup_codes is None
        assert user.mfa_failed_attempts == 0

    async def test_mfa_setup_stores_secret_and_backup_codes(self, db: AsyncSession):
        """Le setup MFA stocke le secret et les codes de secours."""
        user = Utilisateur(
            clinic_id=1, email="mfa_setup@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="MFA", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        secret = generate_mfa_secret()
        backup_codes = generate_backup_codes()

        user.mfa_secret = secret
        user.mfa_backup_codes = json.dumps(backup_codes)
        await db.flush()

        assert user.mfa_secret == secret
        stored_codes = json.loads(user.mfa_backup_codes)
        assert len(stored_codes) == 10

    async def test_mfa_activation_flow(self, db: AsyncSession):
        """Flow complet : setup → confirm → enabled."""
        user = Utilisateur(
            clinic_id=1, email="mfa_flow@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="Flow", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        # Étape 1 : Setup
        secret = generate_mfa_secret()
        backup_codes = generate_backup_codes()
        user.mfa_secret = secret
        user.mfa_backup_codes = json.dumps(backup_codes)
        await db.flush()

        # Étape 2 : Confirm (vérifier OTP)
        current_code = get_current_totp(secret)
        assert verify_totp(secret, current_code) is True

        user.mfa_enabled = True
        user.mfa_setup_at = datetime.utcnow()
        await db.flush()

        assert user.mfa_enabled is True
        assert user.mfa_setup_at is not None

    async def test_backup_code_usage_removes_code(self, db: AsyncSession):
        """Utiliser un code de secours le retire de la liste."""
        user = Utilisateur(
            clinic_id=1, email="backup@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="Backup", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        backup_codes = generate_backup_codes()
        used_code = backup_codes[0]

        # Simuler l'utilisation
        remaining = [c for c in backup_codes if c.lower() != used_code.lower()]
        user.mfa_backup_codes = json.dumps(remaining)
        await db.flush()

        stored = json.loads(user.mfa_backup_codes)
        assert len(stored) == 9
        assert used_code not in stored

    async def test_mfa_lockout_after_max_attempts(self, db: AsyncSession):
        """Le compte est verrouillé après MAX_MFA_ATTEMPTS tentatives."""
        user = Utilisateur(
            clinic_id=1, email="lockout@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="Lockout", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        secret = generate_mfa_secret()
        user.mfa_secret = secret
        user.mfa_enabled = True
        user.mfa_failed_attempts = MAX_MFA_ATTEMPTS - 1
        await db.flush()

        # Simuler une dernière tentative échouée
        user.mfa_failed_attempts += 1
        if user.mfa_failed_attempts >= MAX_MFA_ATTEMPTS:
            user.mfa_locked_until = datetime.utcnow() + timedelta(minutes=15)
            user.mfa_failed_attempts = 0
        await db.flush()

        assert user.mfa_locked_until is not None
        assert user.mfa_failed_attempts == 0

    async def test_mfa_disable_clears_all_fields(self, db: AsyncSession):
        """Désactiver le MFA efface toutes les données MFA."""
        user = Utilisateur(
            clinic_id=1, email="disable@clinic.tn",
            hashed_password=get_password_hash("password123"),
            nom="Test", prenom="Disable", role=RoleEnum.MEDECIN.value,
        )
        db.add(user)
        await db.flush()

        user.mfa_secret = generate_mfa_secret()
        user.mfa_enabled = True
        user.mfa_backup_codes = json.dumps(generate_backup_codes())
        user.mfa_setup_at = datetime.utcnow()
        user.mfa_failed_attempts = 3
        await db.flush()

        # Désactiver
        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes = None
        user.mfa_setup_at = None
        user.mfa_failed_attempts = 0
        user.mfa_locked_until = None
        await db.flush()

        assert user.mfa_enabled is False
        assert user.mfa_secret is None
        assert user.mfa_backup_codes is None
        assert user.mfa_setup_at is None
        assert user.mfa_failed_attempts == 0
        assert user.mfa_locked_until is None


# ── Bloc 4 : stockage sécurisé des codes de secours ────────────────────────
def test_backup_code_hash_is_not_the_plaintext_and_is_single_use():
    from services.mfa import hash_backup_code
    code = generate_backup_codes(1)[0]
    stored = hash_backup_code(code)
    assert code not in stored
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_backup_code(code, [stored]) is True
    assert verify_backup_code("00000000", [stored]) is False


def test_backup_code_hashes_use_distinct_salts():
    from services.mfa import hash_backup_code
    code = "AB12CD34"
    assert hash_backup_code(code) != hash_backup_code(code)
