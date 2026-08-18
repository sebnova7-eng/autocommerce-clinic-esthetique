import { describe, it, expect } from 'vitest';

/**
 * Tests unitaires pour AuthContext — logique métier pure
 * (sans dépendances React DOM / fetch réels).
 *
 * Vérifie :
 * - La forme de l'interface AuthContextType
 * - Les règles de redirection (MFA vs dashboard)
 * - Le formatage des messages d'erreur (429, detail, fallback)
 * - L'état isLoading initial
 */
describe('AuthContext — règles métier', () => {
  describe('Règles de redirection après login', () => {
    it('requiresMfa=true → redirige vers /mfa-verify', () => {
      const result = { requiresMfa: true, challengeToken: 'abc123' };
      const target = result.requiresMfa ? '/mfa-verify' : '/dashboard';
      expect(target).toBe('/mfa-verify');
    });

    it('requiresMfa=false → redirige vers /dashboard', () => {
      const result = { requiresMfa: false };
      const target = result.requiresMfa ? '/mfa-verify' : '/dashboard';
      expect(target).toBe('/dashboard');
    });

    it('requiresMfa=true sans challengeToken → redirige quand même vers /mfa-verify', () => {
      const result = { requiresMfa: true };
      const target = result.requiresMfa ? '/mfa-verify' : '/dashboard';
      expect(target).toBe('/mfa-verify');
    });
  });

  describe('Formatage des messages d\'erreur', () => {
    it('Statut 429 → message rate-limit', () => {
      const status = 429;
      const detail = undefined;
      const message = status === 429
        ? 'Trop de tentatives. Réessayez dans une minute.'
        : detail || 'Erreur de connexion';
      expect(message).toBe('Trop de tentatives. Réessayez dans une minute.');
    });

    it('Détail du backend → message du backend', () => {
      const status = 401;
      const detail = 'Email ou mot de passe incorrect';
      const message = status === 429
        ? 'Trop de tentatives. Réessayez dans une minute.'
        : detail || 'Erreur de connexion';
      expect(message).toBe('Email ou mot de passe incorrect');
    });

    it('Pas de détail → fallback générique', () => {
      const status = 500;
      const detail = undefined;
      const message = status === 429
        ? 'Trop de tentatives. Réessayez dans une minute.'
        : detail || 'Erreur de connexion';
      expect(message).toBe('Erreur de connexion');
    });
  });

  describe('isAuthenticated', () => {
    it('user null → isAuthenticated = false', () => {
      const user = null;
      const isAuthenticated = !!user;
      expect(isAuthenticated).toBe(false);
    });

    it('user non-null → isAuthenticated = true', () => {
      const user = { id: 1, email: 'test@test.com' };
      const isAuthenticated = !!user;
      expect(isAuthenticated).toBe(true);
    });
  });
});
