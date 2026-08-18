import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { authApi, MfaStatusResponse, MfaSetupResponse } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Shield, ShieldCheck, ShieldOff, Copy, Check } from 'lucide-react';

type Step = 'initial' | 'setup' | 'confirm' | 'enabled';

export default function MfaSettings() {
  const [step, setStep] = useState<Step>('initial');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<MfaStatusResponse | null>(null);
  const [setupData, setSetupData] = useState<MfaSetupResponse | null>(null);
  const [confirmOtp, setConfirmOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [copied, setCopied] = useState<number | null>(null);

  // Charger le statut MFA au montage
  useEffect(() => {
    const loadStatus = async () => {
      try {
        const res = await authApi.mfaStatus();
        setStatus(res.data);
        setStep(res.data.enabled ? 'enabled' : 'initial');
      } catch {
        // Si le MFA n'est pas accessible, rester sur initial
      }
    };
    loadStatus();
  }, []);

  // Étape 1 : Démarrer la configuration MFA
  const handleSetup = async () => {
    setIsLoading(true);
    try {
      const res = await authApi.mfaSetup();
      setSetupData(res.data);
      setStep('setup');
      toast.success('Scannez le QR code avec votre application d\'authentification');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la configuration MFA');
    } finally {
      setIsLoading(false);
    }
  };

  // Étape 2 : Confirmer avec le premier OTP
  const handleConfirm = async () => {
    if (confirmOtp.length !== 6) {
      toast.error('Le code doit contenir 6 chiffres');
      return;
    }
    setIsLoading(true);
    try {
      await authApi.mfaConfirm(confirmOtp);
      setStatus({ enabled: true, setup_at: new Date().toISOString() });
      setStep('enabled');
      toast.success('MFA activé avec succès !');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Code invalide');
    } finally {
      setIsLoading(false);
    }
  };

  // Étape 3 : Désactiver le MFA
  const handleDisable = async () => {
    if (!disablePassword) {
      toast.error('Veuillez saisir votre mot de passe');
      return;
    }
    setIsLoading(true);
    try {
      await authApi.mfaDisable(disablePassword);
      setStatus({ enabled: false, setup_at: null });
      setStep('initial');
      setDisablePassword('');
      toast.success('MFA désactivé');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur');
    } finally {
      setIsLoading(false);
    }
  };

  const copyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopied(index);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Sécurité</h1>
          <p className="text-muted-foreground mt-1">
            Gérez l'authentification à deux facteurs (2FA/MFA)
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {status?.enabled ? (
                  <ShieldCheck className="h-6 w-6 text-green-600" />
                ) : (
                  <ShieldOff className="h-6 w-6 text-muted-foreground" />
                )}
                <div>
                  <CardTitle>Authentification à deux facteurs</CardTitle>
                  <CardDescription>
                    {status?.enabled
                      ? 'Protégé par code OTP (Time-Based One-Time Password)'
                      : 'Ajoutez une couche de sécurité à votre compte'}
                  </CardDescription>
                </div>
              </div>
              <Badge variant={status?.enabled ? 'default' : 'secondary'}>
                {status?.enabled ? 'Activé' : 'Désactivé'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* État initial : proposer d'activer */}
            {step === 'initial' && !status?.enabled && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  L'authentification à deux facteurs ajoute une couche de sécurité en requérant
                  un code temporaire en plus de votre mot de passe.
                </p>
                <Button onClick={handleSetup} disabled={isLoading}>
                  <Shield className="mr-2 h-4 w-4" />
                  Configurer le MFA
                </Button>
              </div>
            )}

            {/* État setup : afficher le QR et les codes de secours */}
            {step === 'setup' && setupData && (
              <div className="space-y-6">
                <div className="text-center space-y-3">
                  <p className="text-sm font-medium">1. Scannez ce QR code avec votre application</p>
                  <img
                    src={`data:image/png;base64,${setupData.qr_code_b64}`}
                    alt="QR Code MFA"
                    className="w-48 h-48 mx-auto border rounded-lg"
                  />
                  <p className="text-xs text-muted-foreground">
                    Ou saisissez manuellement : <code className="bg-muted px-1 rounded">{setupData.secret}</code>
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">2. Saisissez le code affiché pour confirmer :</p>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Code à 6 chiffres"
                      value={confirmOtp}
                      onChange={(e) => setConfirmOtp(e.target.value)}
                      maxLength={6}
                    />
                    <Button onClick={handleConfirm} disabled={isLoading || confirmOtp.length !== 6}>
                      Confirmer
                    </Button>
                  </div>
                </div>

                <div className="space-y-2 pt-4 border-t">
                  <p className="text-sm font-medium">3. Codes de secours (sauvegardez-les !) :</p>
                  <p className="text-xs text-muted-foreground">
                    Ces codes à usage unique vous permettent de vous connecter si vous perdez votre téléphone.
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {setupData.backup_codes.map((code, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between bg-muted p-2 rounded text-sm font-mono"
                      >
                        <span>{code}</span>
                        <button
                          onClick={() => copyCode(code, i)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          {copied === i ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* État enabled : proposer de désactiver */}
            {step === 'enabled' && status?.enabled && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Le MFA est actif sur votre compte. Votre compte est protégé par un code OTP à chaque connexion.
                </p>
                <p className="text-xs text-muted-foreground">
                  Activé le : {status.setup_at ? new Date(status.setup_at).toLocaleDateString() : 'N/A'}
                </p>

                <div className="pt-4 border-t space-y-3">
                  <p className="text-sm font-medium">Désactiver le MFA :</p>
                  <div className="flex gap-2">
                    <Input
                      type="password"
                      placeholder="Votre mot de passe"
                      value={disablePassword}
                      onChange={(e) => setDisablePassword(e.target.value)}
                    />
                    <Button
                      variant="destructive"
                      onClick={handleDisable}
                      disabled={isLoading || !disablePassword}
                    >
                      Désactiver
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
