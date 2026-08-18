import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { Video, ExternalLink, Clock, FileText, Plus } from 'lucide-react';

export default function TeleconsultationPage({ rdvId }: { rdvId?: number }) {
  const [isLoading, setIsLoading] = useState(false);
  const [tcData, setTcData] = useState<any>(null);

  useEffect(() => {
    if (rdvId) {
      loadTeleconsultation();
    }
  }, [rdvId]);

  const loadTeleconsultation = async () => {
    try {
      setIsLoading(true);
      const response = await api.get(`/teleconsultation/${rdvId}/lien`);
      setTcData(response.data);
    } catch (err) {
      // Si pas trouvé, on proposera de la créer
      setTcData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!rdvId) return;
    try {
      setIsLoading(true);
      const response = await api.post('/teleconsultation/creer', { rdv_id: rdvId });
      setTcData(response.data);
      toast.success('Téléconsultation créée !');
    } catch (err) {
      toast.error('Erreur lors de la création');
    } finally {
      setIsLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!tcData) return;
    try {
      setIsLoading(true);
      await api.post(`/teleconsultation/${tcData.id}/terminer`, {
        duree: 30, // Exemple
        notes: "Consultation terminée via interface"
      });
      toast.success('Marquée comme terminée');
      loadTeleconsultation();
    } catch (err) {
      toast.error('Erreur');
    } finally {
      setIsLoading(false);
    }
  };

  if (!rdvId) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center h-96 space-y-4">
          <Video className="w-16 h-16 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Aucun rendez-vous sélectionné</h2>
          <p className="text-muted-foreground">Veuillez accéder à une téléconsultation depuis l'agenda.</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Video className="w-8 h-8 text-primary" />
            Téléconsultation
          </h1>
          {tcData && (
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              tcData.statut === 'terminee' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
            }`}>
              {tcData.statut.toUpperCase()}
            </div>
          )}
        </div>

        {!tcData ? (
          <Card className="text-center py-12">
            <CardContent className="space-y-4">
              <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                <Video className="w-8 h-8 text-primary" />
              </div>
              <div className="space-y-2">
                <CardTitle>Prêt pour la visio ?</CardTitle>
                <CardDescription>
                  Générez un lien sécurisé pour démarrer la consultation avec votre patiente.
                </CardDescription>
              </div>
              <Button onClick={handleCreate} disabled={isLoading} size="lg">
                {isLoading ? <Spinner className="mr-2" /> : <Plus className="mr-2 w-4 h-4" />}
                Générer le lien de téléconsultation
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Lien de la consultation</CardTitle>
                <CardDescription>Cliquez sur le bouton ci-dessous pour ouvrir la salle virtuelle Jitsi.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-4 bg-muted rounded-lg font-mono text-sm break-all">
                  {tcData.lien_visio}
                </div>
                <div className="flex gap-4">
                  <Button asChild className="flex-1" size="lg">
                    <a href={tcData.lien_visio} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="mr-2 w-4 h-4" />
                      Rejoindre la visio
                    </a>
                  </Button>
                  {tcData.statut !== 'terminee' && (
                    <Button variant="outline" onClick={handleComplete} disabled={isLoading}>
                      Marquer terminée
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Détails
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="flex justify-between text-muted-foreground">
                    <span>RDV ID</span>
                    <span className="text-foreground">#{rdvId}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Plateforme</span>
                    <span className="text-foreground">Jitsi Meet</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <FileText className="w-4 h-4" /> Notes
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <textarea 
                    className="w-full min-h-[100px] p-2 text-sm border rounded-md"
                    placeholder="Saisissez vos notes ici..."
                  ></textarea>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
