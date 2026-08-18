import React, { createContext, useContext, useState, useCallback } from 'react';
import { authApi, setAccessToken, clearTokens, getAccessToken, UserOut } from '@/lib/api';
import { toast } from 'sonner';

interface AuthContextType {
  user: UserOut | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<{ requiresMfa: boolean; challengeToken?: string }>;
  verifyMfa: (challengeToken: string, otp: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  React.useEffect(() => {
    const initAuth = async () => {
      const token = getAccessToken();
      if (token) {
        try {
          const response = await authApi.me();
          setUser(response.data);
        } catch (err) {
          console.error("Failed to rehydrate session", err);
          clearTokens();
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<{ requiresMfa: boolean; challengeToken?: string }> => {
    setIsLoading(true);
    try {
      const response = await authApi.login(email, password);

      // Si le MFA est activé, le backend renvoie un challenge_token signé
      // (5 min) plutôt que des tokens d'accès — rien d'autre à faire ici
      // que de le transmettre à l'écran de saisie OTP.
      if ('mfa_required' in response.data) {
        return { requiresMfa: true, challengeToken: response.data.challenge_token };
      }

      const { access_token } = response.data;
      setAccessToken(access_token);

      // Fetch user info
      const userResponse = await authApi.me();
      setUser(userResponse.data);

      toast.success('Connecté avec succès');
      return { requiresMfa: false };
    } catch (err: any) {
      const message =
        err.response?.status === 429
          ? 'Trop de tentatives. Réessayez dans une minute.'
          : err.response?.data?.detail || 'Erreur de connexion';
      toast.error(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const verifyMfa = useCallback(async (challengeToken: string, otp: string) => {
    setIsLoading(true);
    try {
      const response = await authApi.verifyMfa(challengeToken, otp);
      const { access_token } = response.data;

      setAccessToken(access_token);

      // Fetch user info
      const userResponse = await authApi.me();
      setUser(userResponse.data);

      toast.success('Connexion MFA réussie');
    } catch (err: any) {
      const message =
        err.response?.status === 429
          ? 'Trop de tentatives. Compte verrouillé temporairement.'
          : err.response?.data?.detail || 'Code OTP invalide ou session expirée';
      toast.error(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    void authApi.logout().catch(() => undefined);
    setUser(null);
    clearTokens();
    toast.success('Déconnecté');
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const response = await authApi.me();
      setUser(response.data);
    } catch (err) {
      logout();
    }
  }, [logout]);

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    verifyMfa,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
