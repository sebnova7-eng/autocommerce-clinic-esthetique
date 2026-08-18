"""add CHECK constraint on avis_clients.plateforme

Revision ID: bloc8b_avis_plateforme_enum
Revises: bloc3_simulation_ia
Create Date: 2026-07-29 21:42:00.000000

Correctif Bug #8 (audit) :
le champ ``avis_clients.plateforme`` était un ``String(20)`` sans
contrainte, ce qui acceptait n'importe quelle chaîne (ex: ``FACEBOOK``
au lieu de ``facebook``), cassant les filtres du dashboard e-réputation
et les appels d'auto-reply IA côté services/reputation.py.

Cette migration ajoute :
- un ``CheckConstraint`` ``plateforme IN ('google','instagram','facebook')``
- un nettoyage (UPDATE) des éventuelles valeurs hors-énumération déjà
  présentes (logs.warn + bascule vers 'google' par défaut pour
  préserver l'historique) avant l'application de la contrainte.

La cohérence avec l'enum Python ``PlateformeAvis`` côté
``models/database.py`` est garantie par les deux côtés.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bloc8b_avis_plateforme_enum"
down_revision: Union[str, None] = "bloc3_simulation_ia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALLOWED = ("google", "instagram", "facebook")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "avis_clients" not in inspector.get_table_names():
        # Aucun avis existant : appliquer directement la contrainte.
        op.create_check_constraint(
            "ck_avis_plateforme_enum",
            "avis_clients",
            "plateforme IN ('google', 'instagram', 'facebook')",
        )
        return

    # 1. Nettoyage défensif des valeurs éventuellement hors-énumération.
    # Toute ligne "exotique" est basculée sur 'google' pour préserver
    # l'historique tout en respectant la contrainte.
    rows = bind.execute(
        sa.text(
            "SELECT id, plateforme FROM avis_clients "
            "WHERE plateforme NOT IN ('google','instagram','facebook')"
        )
    ).fetchall()
    if rows:
        print(
            f"[bloc8b] Nettoyage defensif : {len(rows)} ligne(s) "
            "avis_clients avec plateforme hors enum -> 'google'"
        )
        bind.execute(
            sa.text(
                "UPDATE avis_clients SET plateforme='google' "
                "WHERE plateforme NOT IN ('google','instagram','facebook')"
            )
        )

    # 2. Ajout effectif de la contrainte CHECK.
    with op.batch_alter_table("avis_clients") as batch_op:
        batch_op.create_check_constraint(
            "ck_avis_plateforme_enum",
            "plateforme IN ('google', 'instagram', 'facebook')",
        )


def downgrade() -> None:
    with op.batch_alter_table("avis_clients") as batch_op:
        batch_op.drop_constraint("ck_avis_plateforme_enum", type_="check")
