#!/usr/bin/env python3
"""
AutoCommerce Clinic — Script CLI d'ingestion simulée d'avis Google.

Correctif Bug #7 (audit) :
L'endpoint ``POST /social/avis/ingestion-google-test`` exposait un faux
injecteur d'avis ("Jean Dupont, 5★, Superbe expérience…") accessible
aux admins. Un admin distrait pouvait polluer la table ``avis_clients``
avec des avis fictifs qui apparaissaient dans le dashboard e-réputation.

Ce script remplace cet endpoint :
- Il n'est JAMAIS servi par FastAPI (pas d'exposition HTTP).
- Il exige une confirmation explicite (--confirm) avant toute écriture.
- Il accepte les paramètres (plateforme, note, texte, auteur) en CLI
  — utile pour les smoke-tests et les démos.
- En production, le connecter à une vraie API Google My Business
  (oauth2 + refresh token). Ce script sert de bouchon local pour le
  développement.

Usage :
    python scripts/ingest_google_review.py \
        --plateforme google --note 5 \
        --texte "Très bonne expérience" \
        --auteur "Jean Dupont" --confirm
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Permet l'exécution depuis la racine du dépôt ou depuis scripts/.
ROOT = Path(__file__).resolve().parent.parent / "api-server"
sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from api.deps import get_db  # noqa: E402
from models.database import AvisClient  # noqa: E402


async def ingest(
    plateforme: str,
    note: int,
    texte: str,
    auteur: str,
    clinic_id: int,
    confirm: bool,
) -> int:
    """Insère un avis en base après confirmation explicite."""
    if not confirm:
        print(
            "Refus : passez --confirm pour valider l'écriture en base.\n"
            "Cet argument existe pour éviter toute pollution accidentelle\n"
            "de la table avis_clients (audit Bug #7).",
            file=sys.stderr,
        )
        return 2

    if not 1 <= note <= 5:
        print(f"Note invalide : {note} (attendu entre 1 et 5).", file=sys.stderr)
        return 3

    if plateforme not in {"google", "facebook", "instagram", "tiktok"}:
        print(
            f"Plateforme '{plateforme}' non reconnue. Attendu : "
            "google | facebook | instagram | tiktok.",
            file=sys.stderr,
        )
        return 4

    db_gen = get_db()
    db: AsyncSession = await db_gen.__anext__()
    try:
        avis = AvisClient(
            clinic_id=clinic_id,
            plateforme=plateforme,
            note=note,
            texte=texte,
            auteur_nom=auteur,
            statut="nouveau",
        )
        db.add(avis)
        await db.flush()
        print(f"OK : avis inséré id={avis.id} plateforme={plateforme} note={note}")
        return 0
    finally:
        await db_gen.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingère un avis simulé en base (CLI — Bug #7 audit fix).",
    )
    parser.add_argument("--plateforme", default="google",
                        choices=["google", "facebook", "instagram", "tiktok"])
    parser.add_argument("--note", type=int, default=5)
    parser.add_argument("--texte", default="Smoke-test d'ingestion (audit Bug #7).")
    parser.add_argument("--auteur", default="Smoke Tester")
    parser.add_argument("--clinic-id", type=int, default=1)
    parser.add_argument("--confirm", action="store_true",
                        help="Confirme explicitement l'écriture en base.")
    args = parser.parse_args()

    return asyncio.run(ingest(
        plateforme=args.plateforme,
        note=args.note,
        texte=args.texte,
        auteur=args.auteur,
        clinic_id=args.clinic_id,
        confirm=args.confirm,
    ))


if __name__ == "__main__":
    sys.exit(main())
