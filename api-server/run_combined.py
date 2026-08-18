"""
Serveur combiné : API FastAPI + Frontend statique
Sert le frontend buildé en prod ET l'API backend sur le même port.
"""
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import os

# Charger l'env
from dotenv import load_dotenv
load_dotenv()

# Importer l'app principale
from main import app

# Déterminer le chemin du frontend de manière relative au script
BASE_DIR = Path(__file__).resolve().parent.parent
frontend_dir = BASE_DIR / "autocommerce-app" / "dist" / "public"

# Servir les fichiers statiques (assets)
if (frontend_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="static_assets")
else:
    print(f"Warning: Static assets directory not found at {frontend_dir / 'assets'}")

if (frontend_dir / "__manus__").exists():
    app.mount("/__manus__", StaticFiles(directory=str(frontend_dir / "__manus__")), name="manus_static")

# Catch-all pour le SPA (toutes les routes non-API servent index.html)
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Catch-all pour les routes du SPA frontend."""
    # Ignorer les routes qui commencent par api
    if full_path.startswith("api/"):
        return JSONResponse({"error": "API endpoint not found"}, status_code=404)
        
    # Ne pas interférer avec les routes API existantes
    file_path = frontend_dir / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return {"error": "Frontend not built. Please run 'pnpm build' in autocommerce-app directory."}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
