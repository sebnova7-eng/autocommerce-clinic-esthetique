"""
AutoCommerce Clinic — Service Social CRM

Inbox unifié (WhatsApp/Instagram/Facebook/TikTok), réponse automatique
par mots-clés, planification de posts, analytics.

Limite assumée : WhatsApp est réellement branché (via
services/whatsapp_service.py, Meta Business API). Instagram, Facebook
et TikTok n'ont PAS de connexion réelle ici — publier/vérifier dessus
nécessite un compte développeur approuvé par ces plateformes, qu'on
ne peut pas obtenir sans les identifiants du client. Ce module expose
donc le point d'intégration (PLATFORM_CONNECTORS) : brancher une
vraie clé API dessus suffit à activer la plateforme, sans changer le
reste du code.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func

from models.database import SocialMessage, SocialPost, Patient
from services.whatsapp_service import send_whatsapp_message

PLATEFORMES_VALIDES = {"whatsapp", "instagram", "facebook", "tiktok"}

# Règles de réponse automatique — mot-clé (insensible à la casse) → réponse.
# Volontairement simple et déterministe : un vrai moteur NLU peut être
# branché ici plus tard sans changer l'API du module.
REGLES_AUTO_REPONSE = [
    (["horaire", "ouvert", "ferme"], "Nous sommes ouverts du lundi au samedi, 9h-18h. Pour un RDV, dites-nous simplement quel jour vous convient !"),
    (["rdv", "rendez-vous", "rendez vous"], "Pour prendre RDV, précisez le soin souhaité et vos disponibilités — un membre de l'équipe vous recontacte rapidement."),
    (["prix", "tarif", "combien"], "Les tarifs dépendent du soin — dites-nous lequel vous intéresse et on vous envoie le détail."),
]


def _match_auto_reply(contenu: str) -> Optional[str]:
    texte = contenu.lower()
    for mots_cles, reponse in REGLES_AUTO_REPONSE:
        if any(m in texte for m in mots_cles):
            return reponse
    return None


async def _find_patient_by_contact(plateforme: str, contact_id: str, db, *, clinic_id: int) -> Optional[Patient]:
    if plateforme != "whatsapp":
        return None
    result = await db.execute(
        select(Patient).where(
            ((Patient.whatsapp_phone == contact_id) | (Patient.telephone == contact_id)),
            Patient.clinic_id == clinic_id,
        )
    )
    return result.scalar_one_or_none()


async def receive_message(plateforme: str, contact_id: str, contenu: str, db,
                           contact_nom: Optional[str] = None, *, clinic_id: int) -> dict:
    if plateforme not in PLATEFORMES_VALIDES:
        raise ValueError(f"Plateforme non supportée : {plateforme}")

    patient = await _find_patient_by_contact(plateforme, contact_id, db, clinic_id=clinic_id)

    message = SocialMessage(
        clinic_id=clinic_id, plateforme=plateforme, contact_id=contact_id, contact_nom=contact_nom,
        direction="entrant", contenu=contenu, statut="nouveau",
        patient_id=patient.id if patient else None,
    )
    db.add(message)
    await db.flush()

    auto_reponse = _match_auto_reply(contenu)
    reponse_reussie = False
    if auto_reponse:
        reponse = await send_reply(message.id, auto_reponse, db, automatique=True, clinic_id=clinic_id)
        reponse_reussie = reponse.statut == "traite"

    return {"message": message, "auto_reponse_envoyee": reponse_reussie}


async def send_reply(message_id: int, contenu: str, db, automatique: bool = False, *, clinic_id: int) -> SocialMessage:
    result = await db.execute(select(SocialMessage).where(
        SocialMessage.id == message_id, SocialMessage.clinic_id == clinic_id
    ))
    original = result.scalar_one_or_none()
    if not original:
        raise ValueError("Message non trouvé")

    dispatch = await _dispatch_to_platform(original.plateforme, original.contact_id, contenu)

    reponse = SocialMessage(
        clinic_id=clinic_id, plateforme=original.plateforme, contact_id=original.contact_id,
        contact_nom=original.contact_nom, direction="sortant", contenu=contenu,
        statut="traite" if dispatch["envoye"] else "echec",
        reponse_auto_envoyee=automatique, patient_id=original.patient_id,
    )
    db.add(reponse)

    original.statut = "repondu" if dispatch["envoye"] else original.statut
    await db.flush()
    return reponse


async def _dispatch_to_platform(plateforme: str, contact_id: str, contenu: str) -> dict:
    """Point d'intégration unique. WhatsApp est réellement branché ;
    les autres plateformes retournent honnêtement 'non connectée' tant
    qu'aucune clé API n'est configurée — pas de faux succès."""
    if plateforme == "whatsapp":
        result = await send_whatsapp_message(contact_id, contenu)
        # CORRECTION AUDIT : dev_mode ne doit PAS être considéré comme envoyé
        status = result.get("status", "")
        return {
            "envoye": status == "sent",
            "dev_mode": status == "dev_mode",
            "detail": result,
        }

    # Instagram / Facebook / TikTok : nécessitent un compte développeur
    # approuvé par la plateforme (Meta Business, TikTok for Business).
    return {"envoye": False, "detail": f"Plateforme '{plateforme}' non connectée — clé API à configurer"}


async def list_messages(db, plateforme: Optional[str] = None, statut: Optional[str] = None, *, clinic_id: int) -> list[SocialMessage]:
    query = select(SocialMessage).where(SocialMessage.clinic_id == clinic_id)
    if plateforme:
        query = query.where(SocialMessage.plateforme == plateforme)
    if statut:
        query = query.where(SocialMessage.statut == statut)
    result = await db.execute(query.order_by(SocialMessage.created_at.desc()))
    return list(result.scalars().all())


# ── Posts ──────────────────────────────────────────────────

async def create_post(data: dict, created_by: int, db, *, clinic_id: int) -> SocialPost:
    if data["plateforme"] not in PLATEFORMES_VALIDES:
        raise ValueError(f"Plateforme non supportée : {data['plateforme']}")

    post = SocialPost(
        clinic_id=clinic_id, plateforme=data["plateforme"], contenu=data["contenu"],
        media_url=data.get("media_url"),
        date_publication_prevue=data.get("date_publication_prevue"),
        statut="planifie" if data.get("date_publication_prevue") else "brouillon",
        created_by=created_by,
    )
    db.add(post)
    await db.flush()
    return post


async def publier_post(post_id: int, db, *, clinic_id: int) -> SocialPost:
    result = await db.execute(select(SocialPost).where(
        SocialPost.id == post_id, SocialPost.clinic_id == clinic_id
    ))
    post = result.scalar_one_or_none()
    if not post:
        raise ValueError("Post non trouvé")
    if post.statut == "publie":
        raise ValueError("Post déjà publié")

    dispatch = await _dispatch_to_platform(post.plateforme, "broadcast", post.contenu)
    if dispatch["envoye"]:
        post.statut = "publie"
        post.date_publication_reelle = datetime.utcnow()
    else:
        post.statut = "echec"
        post.erreur = dispatch["detail"] if isinstance(dispatch["detail"], str) else "Échec de publication"

    await db.flush()
    return post


async def enregistrer_metriques(post_id: int, likes: int, commentaires: int,
                                 partages: int, impressions: int, db, *, clinic_id: int) -> SocialPost:
    result = await db.execute(select(SocialPost).where(
        SocialPost.id == post_id, SocialPost.clinic_id == clinic_id
    ))
    post = result.scalar_one_or_none()
    if not post:
        raise ValueError("Post non trouvé")

    post.likes = likes
    post.commentaires = commentaires
    post.partages = partages
    post.impressions = impressions
    await db.flush()
    return post


async def list_posts(db, plateforme: Optional[str] = None, statut: Optional[str] = None, *, clinic_id: int) -> list[SocialPost]:
    query = select(SocialPost).where(SocialPost.clinic_id == clinic_id)
    if plateforme:
        query = query.where(SocialPost.plateforme == plateforme)
    if statut:
        query = query.where(SocialPost.statut == statut)
    result = await db.execute(query.order_by(SocialPost.created_at.desc()))
    return list(result.scalars().all())


# ── Analytics ────────────────────────────────────────────────

async def get_analytics(db, *, clinic_id: int) -> dict:
    msgs_result = await db.execute(
        select(SocialMessage.plateforme, SocialMessage.statut, func.count(SocialMessage.id))
        .where(SocialMessage.clinic_id == clinic_id).group_by(SocialMessage.plateforme, SocialMessage.statut)
    )
    par_plateforme: dict = {}
    for plateforme, statut, count in msgs_result.all():
        par_plateforme.setdefault(plateforme, {})[statut] = count

    posts_result = await db.execute(
        select(
            SocialPost.plateforme,
            func.count(SocialPost.id),
            func.coalesce(func.sum(SocialPost.likes), 0),
            func.coalesce(func.sum(SocialPost.commentaires), 0),
            func.coalesce(func.sum(SocialPost.impressions), 0),
        ).where(SocialPost.statut == "publie", SocialPost.clinic_id == clinic_id).group_by(SocialPost.plateforme)
    )
    posts_stats = {
        plateforme: {"nb_posts": nb, "likes": likes, "commentaires": comments, "impressions": impressions}
        for plateforme, nb, likes, comments, impressions in posts_result.all()
    }

    return {"messages": par_plateforme, "posts": posts_stats}
