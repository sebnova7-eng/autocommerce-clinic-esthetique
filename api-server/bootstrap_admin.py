#!/usr/bin/env python3
"""
AutoCommerce Clinic — Bootstrap du premier compte administrateur.

Ce script vit dans `api-server/` pour être inclus dans l'image Docker
construite avec `api-server/Dockerfile` (contexte de build limité à ce
répertoire). Il peut donc être exécuté directement dans le conteneur :

    docker compose --env-file .env.clinic -f docker-compose.clinic.yml \
      run --rm api python bootstrap_admin.py \
      --email directrice@clinic.tn --nom Trabelsi --prenom Amel

Pour un usage non interactif (CI/validation), on peut fournir le mot de
passe via stdin :

    printf 'MotDePasseTresSolide123\n' | docker compose -T \
      --env-file .env.clinic -f docker-compose.clinic.yml \
      run --rm api python bootstrap_admin.py \
      --email directrice@clinic.tn --nom Trabelsi --prenom Amel \
      --password-stdin
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from middleware.auth import get_password_hash
from models.database import RoleEnum, Utilisateur


async def bootstrap(
    email: str,
    nom: str,
    prenom: str,
    password: str,
    role: str,
    *,
    clinic_id: int = 1,
    force: bool = False,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sessionmaker() as db:
            existing = await db.execute(select(Utilisateur).where(Utilisateur.email == email))
            if existing.scalar_one_or_none():
                print(f"Un compte existe déjà avec l'email {email}. Rien à faire.")
                return

            any_admin = await db.execute(
                select(Utilisateur).where(
                    Utilisateur.role.in_([RoleEnum.DIRECTRICE.value, RoleEnum.ADMIN.value])
                )
            )
            if any_admin.scalar_one_or_none() and not force:
                confirm = input(
                    "Un compte DIRECTRICE/ADMIN existe déjà sur cette base. "
                    "Créer quand même ce nouveau compte ? [o/N] "
                )
                if confirm.strip().lower() != "o":
                    print("Annulé.")
                    return

            user = Utilisateur(
                clinic_id=clinic_id,
                email=email,
                hashed_password=get_password_hash(password),
                nom=nom,
                prenom=prenom,
                role=role,
                is_active=True,
            )
            db.add(user)
            await db.commit()
            print(f"Compte créé : {email} ({role}).")
    finally:
        await engine.dispose()


def _read_password_from_stdin() -> str:
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        print("Aucun mot de passe reçu sur stdin.", file=sys.stderr)
        raise SystemExit(1)
    return password


def _read_password_interactively() -> str:
    password = getpass.getpass("Mot de passe du compte : ")
    confirm = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirm:
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        raise SystemExit(1)
    return password


def _validate_password(password: str) -> None:
    if len(password) < 12:
        print("Le mot de passe doit faire au moins 12 caractères.", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crée le premier compte administrateur")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nom", required=True)
    parser.add_argument("--prenom", required=True)
    parser.add_argument(
        "--role",
        default=RoleEnum.DIRECTRICE.value,
        choices=[RoleEnum.DIRECTRICE.value, RoleEnum.ADMIN.value],
        help="Rôle du compte créé (défaut : directrice)",
    )
    parser.add_argument(
        "--clinic-id",
        type=int,
        default=1,
        help="Identifiant clinique du compte créé (défaut : 1)",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Lit le mot de passe depuis stdin (utile en Docker/CI).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ne redemande pas confirmation si un autre compte admin existe déjà.",
    )
    args = parser.parse_args()

    password = _read_password_from_stdin() if args.password_stdin else _read_password_interactively()
    _validate_password(password)

    asyncio.run(
        bootstrap(
            args.email,
            args.nom,
            args.prenom,
            password,
            args.role,
            clinic_id=args.clinic_id,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
