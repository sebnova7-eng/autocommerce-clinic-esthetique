"""
AutoCommerce Clinic — Authentification Multi-Facteurs (MFA)

Implémentation TOTP (Time-Based One-Time Password) selon RFC 6238.
Utilise pyotp pour la génération/vérification, stocke le secret chiffré
dans la base de données. Génère 10 codes de secours à usage unique
lors de l'activation.

Flux :
  1. POST /auth/mfa/setup        → retourne secret + QR + backup_codes
  2. POST /auth/mfa/confirm      → vérifie le premier OTP, active MFA
  3. POST /auth/mfa/verify       → vérifie OTP lors de la connexion
  4. POST /auth/mfa/disable      → désactive MFA (mot de passe requis)
"""
import hashlib
import io
import secrets
import hmac

import pyotp
import qrcode

from config import get_settings

settings = get_settings()

# Durée de validité d'un OTP TOTP (30 secondes standard)
TOTP_PERIOD = 30
TOTP_DIGITS = 6

# Nombre de codes de secours générés
BACKUP_CODE_COUNT = 10

# Durée max d'un challenge MFA (5 minutes)
MFA_CHALLENGE_EXPIRY_MINUTES = 5

# Nombre max d'essais OTP avant verrouillage
MAX_MFA_ATTEMPTS = 5


def generate_mfa_secret() -> str:
    """Génère un secret TOTP aléatoire (base32)."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, clinic_name: str) -> str:
    """Retourne l'URI OTPAuth pour le QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email,
        issuer_name=clinic_name
    )


def generate_qr_code(uri: str) -> bytes:
    """Génère un QR code PNG 300x300px pour l'URI OTPAuth."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    """Génère des codes de secours à usage unique.
    
    Chaque code est un hash SHA-256 d'un token aléatoire,
    tronqué aux 8 premiers caractères hexadécimaux pour facilité de saisie.
    """
    codes = []
    for _ in range(count):
        token = secrets.token_hex(16)
        code = hashlib.sha256(token.encode()).hexdigest()[:8]
        codes.append(code)
    return codes


BACKUP_HASH_ALGORITHM = "pbkdf2_sha256"
BACKUP_HASH_ITERATIONS = 120_000


def hash_backup_code(code: str) -> str:
    """Retourne un hash PBKDF2 salé ; le code brut n'est jamais stocké."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", code.strip().lower().encode("utf-8"), salt,
        BACKUP_HASH_ITERATIONS,
    )
    return f"{BACKUP_HASH_ALGORITHM}${BACKUP_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_hashed_backup_code(code: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != BACKUP_HASH_ALGORITHM:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", code.strip().lower().encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def verify_backup_code(code: str, backup_codes: list[str]) -> bool:
    """Vérifie un code contre des hashes ; les valeurs brutes restent tolérées
    uniquement pour compatibilité avec les tests/outils historiques, jamais par
    le flux de stockage de production."""
    normalized = code.strip().lower()
    return any(
        _verify_hashed_backup_code(normalized, stored) if "$" in stored
        else hmac.compare_digest(normalized, stored.strip().lower())
        for stored in backup_codes if stored
    )


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [hash_backup_code(code) for code in codes]


def verify_totp(secret: str, otp: str, window: int = 1) -> bool:
    """Vérifie un code OTP TOTP avec une fenêtre de ±1 période."""
    totp = pyotp.TOTP(secret)
    return totp.verify(otp, valid_window=window)


def get_current_totp(secret: str) -> str:
    """Retourne le code TOTP actuel (pour les tests uniquement)."""
    totp = pyotp.TOTP(secret)
    return totp.now()
