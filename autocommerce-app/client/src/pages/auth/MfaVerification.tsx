import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLocation } from 'wouter';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';
import { useBranding } from '@/contexts/BrandingContext';
import { Spinner } from '@/components/ui/spinner';
import { Shield } from 'lucide-react';
import { toast } from 'sonner';
import { getMfaChallengeToken, clearMfaChallengeToken } from '@/lib/api';

/**
 * Page de vérification MFA (2FA)
 *
 * Affichée après login quand le serveur demande une vérification MFA.
 * Le challenge_token vient de Login.tsx (gardé en mémoire, jamais en
 * sessionStorage) ; s'il est absent — page rechargée, accès direct à
 * l'URL — on renvoie proprement vers /login plutôt que d'appeler l'API
 * avec un token vide.
 */
export default function MfaVerification() {
  const { verifyMfa, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const { branding } = useBranding();
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const challengeToken = getMfaChallengeToken();

  useEffect(() => {
    if (!challengeToken) {
      toast.error('Session expirée, veuillez vous reconnecter');
      setLocation('/login');
    }
  }, [challengeToken, setLocation]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (otp.length !== 6) {
      setError('Le code doit contenir 6 chiffres');
      return;
    }
    if (!challengeToken) {
      return;
    }

    try {
      await verifyMfa(challengeToken, otp);
      clearMfaChallengeToken();
      setLocation('/dashboard');
    } catch (err: any) {
      const message =
        err.response?.status === 429
          ? 'Trop de tentatives. Compte verrouillé temporairement.'
          : err.response?.data?.detail || 'Code invalide. Veuillez réessayer.';
      setError(message);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <div>
            <CardTitle className="text-2xl">{branding?.nom_clinique || 'Clinique'}</CardTitle>
            <CardDescription>
              Vérification en deux étapes
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2 text-center">
              <p className="text-sm text-muted-foreground">
                Saisissez le code à 6 chiffres généré par votre application d'authentification.
              </p>
            </div>

            <div className="flex justify-center">
              <InputOTP
                maxLength={6}
                value={otp}
                onChange={(value) => {
                  setOtp(value);
                  setError('');
                }}
              >
                <InputOTPGroup>
                  <InputOTPSlot index={0} />
                  <InputOTPSlot index={1} />
                  <InputOTPSlot index={2} />
                  <InputOTPSlot index={3} />
                  <InputOTPSlot index={4} />
                  <InputOTPSlot index={5} />
                </InputOTPGroup>
              </InputOTP>
            </div>

            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={isLoading || otp.length !== 6}
            >
              {isLoading ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Vérification...
                </>
              ) : (
                'Vérifier'
              )}
            </Button>
          </form>

          <p className="text-xs text-muted-foreground text-center mt-4">
            Si vous n'avez pas accès à votre code, contactez l'administrateur.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
