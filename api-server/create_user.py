#!/usr/bin/env python
"""Créer un utilisateur admin pour l'application via variables d'environnement."""

import os
import sys
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

def main():
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    database_url = os.getenv("DATABASE_URL")

    if not all([admin_email, admin_password, database_url]):
        print("Erreur : ADMIN_EMAIL, ADMIN_PASSWORD et DATABASE_URL doivent être définis.")
        sys.exit(1)

    # Convert asyncpg to psycopg2 if necessary for the script
    sync_db_url = database_url.replace("asyncpg", "psycopg2")
    
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    engine = create_engine(sync_db_url)
    
    try:
        with engine.connect() as conn:
            hashed_pwd = pwd_context.hash(admin_password)
            conn.execute(text('''
            INSERT INTO utilisateurs (
                email, nom, prenom, hashed_password, role, clinic_id, 
                created_at, updated_at, taux_commission, is_active, mfa_enabled, mfa_failed_attempts
            )
            VALUES (
                :email, :nom, :prenom, :pwd, :role, :clinic_id, 
                NOW(), NOW(), :commission, true, false, 0
            )
            ON CONFLICT (email) DO UPDATE SET
                hashed_password = EXCLUDED.hashed_password,
                updated_at = NOW()
            '''), {
                'email': admin_email, 
                'nom': 'Admin', 
                'prenom': 'Clinic', 
                'pwd': hashed_pwd, 
                'role': 'admin', 
                'clinic_id': 1, 
                'commission': 0.0
            })
            conn.commit()
            print(f'✓ Utilisateur admin mis à jour/créé : {admin_email}')
    except Exception as e:
        print(f"Erreur lors de la création de l'utilisateur : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
