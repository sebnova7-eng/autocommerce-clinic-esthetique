import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLocation } from 'wouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useBranding } from '@/contexts/BrandingContext';
import { Spinner } from '@/components/ui/spinner';
import { setMfaChallengeToken } from '@/lib/api';

/**
 * Login Page
 * 
 * Design: Professional medical SaaS login
 * - Centered card layout
 * - Logo from branding
 * - Email + password form
 * - MFA flow : si le login retourne un challenge_token, redirige vers /mfa-verify
 * - Rate limiting awareness (429 handling)
 * - Error messages from backend
 */
export default function Login() {
  const { login, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const { branding } = useBranding();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const result = await login(email, password);
      if (result.requiresMfa) {
        if (result.challengeToken) {
          setMfaChallengeToken(result.challengeToken);
        }
        setLocation('/mfa-verify');
      } else {
        setLocation('/dashboard');
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      let message = 'Erreur de connexion';
      if (err.response?.status === 429) {
        message = 'Trop de tentatives. Réessayez dans une minute.';
      } else if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map((item: any) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item))).join(', ');
      } else if (detail && typeof detail === 'object') {
        message = JSON.stringify(detail);
      }
      setError(message);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-4 text-center">
          {branding?.logo_url && (
            <img
              src={branding.logo_url}
              alt="Logo"
              className="h-16 w-16 mx-auto object-contain"
            />
          )}
          <div>
            <CardTitle className="text-2xl">{branding?.nom_clinique || 'Clinique'}</CardTitle>
            <CardDescription>Connectez-vous à votre compte</CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="votre@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Connexion en cours...
                </>
              ) : (
                'Se connecter'
              )}
            </Button>
          </form>

          <p className="text-xs text-muted-foreground text-center mt-4">
            Données médicales sécurisées • Accès personnel
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
