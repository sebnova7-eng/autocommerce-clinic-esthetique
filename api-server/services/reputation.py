"""
AutoCommerce Clinic — Gestion de l'E-réputation
Intégration OpenAI pour suggestions de réponses aux avis clients.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import AvisClient
from config import get_settings
from core.llm_client import LLMUnavailable, get_llm_client

settings = get_settings()


DEFAULT_OPENAI_MODEL = "gpt-4o"


def _get_model_name() -> str:
    """Renvoie le nom de modèle OpenAI à utiliser.

    Correctif Bug #6 (audit) : si ``settings.openai_model`` est absent
    ou laisse une chaîne vide, ``model=None`` fait echouer
    ``client.chat.completions.create`` au premier appel. La constante
    ``DEFAULT_OPENAI_MODEL = "gpt-4o"`` est utilisée comme garde-fou.
    Le rapport d'audit mentionne explicitement GPT-4o : la valeur par
    defaut dans ``config.py`` est deja ``"gpt-4o"``, mais cette
    double-securite evite toute regression si un dev met
    ``OPENAI_MODEL=`` dans son environment.
    """
    model = getattr(settings, "openai_model", None)
    if not model or not str(model).strip():
        return DEFAULT_OPENAI_MODEL
    return str(model).strip()


async def generer_reponse_ia(
    avis: AvisClient, db: AsyncSession, *, budget_subject: str | None = None,
) -> str:
    """Génère une réponse suggérée par l'IA pour un avis client."""
    
    system_prompt = (
        "Vous êtes le community manager d'une clinique d'esthétique haut de gamme (AutoCommerce Clinic). "
        "Votre ton doit être élégant, professionnel et empathique. "
        "RÈGLES CRITIQUES : "
        "1. Ne faites JAMAIS de promesse médicale ou de garantie de résultat. "
        "2. Ne faites JAMAIS de diagnostic. "
        "3. Remerciez le client pour son avis. "
        "4. Si l'avis est négatif, restez courtois et proposez un échange en privé. "
        "5. La réponse doit être concise et raffinée."
    )
    
    user_content = f"Plateforme : {avis.plateforme}\nNote : {avis.note}/5\nAvis : {avis.texte}\nAuteur : {avis.auteur_nom}"
    
    llm = get_llm_client(settings)
    response = await llm.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        model=_get_model_name(),
        temperature=0.7,
        max_tokens=500,
        budget_subject=budget_subject or f"clinic:{avis.clinic_id}:reputation",
        budget_clinic_id=avis.clinic_id,
    )
    if isinstance(response, LLMUnavailable):
        raise RuntimeError(f"IA réputation indisponible : {response.reason}")
    reponse_suggeree = response.text.strip()
    
    # Mettre à jour l'avis
    avis.reponse_suggeree_ia = reponse_suggeree
    avis.statut = "suggere"
    await db.flush()
    
    return reponse_suggeree

async def valider_et_publier(
    avis_id: int, reponse_finale: str, db: AsyncSession,
    clinic_id: int | None = None,
) -> AvisClient:
    """Valide la réponse et marque l'avis comme publié dans sa clinique."""
    stmt = select(AvisClient).where(AvisClient.id == avis_id)
    if clinic_id is not None:
        stmt = stmt.where(AvisClient.clinic_id == clinic_id)
    result = await db.execute(stmt)
    avis = result.scalar_one_or_none()
    
    if not avis:
        raise ValueError("Avis non trouvé")
        
    avis.reponse_publiee = reponse_finale
    avis.statut = "publie"
    await db.flush()
    
    return avis

async def get_avis(
    db: AsyncSession, plateforme: Optional[str] = None,
    clinic_id: int | None = None,
) -> List[AvisClient]:
    """Récupère la liste des avis de la clinique courante."""
    query = select(AvisClient).order_by(AvisClient.created_at.desc())
    if clinic_id is not None:
        query = query.where(AvisClient.clinic_id == clinic_id)
    if plateforme:
        query = query.where(AvisClient.plateforme == plateforme)
        
    result = await db.execute(query)
    return list(result.scalars().all())
