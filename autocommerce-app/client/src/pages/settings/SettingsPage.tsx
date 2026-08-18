import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, BrandingResponse, settingsApi } from '@/lib/api';
import { useBranding } from '@/contexts/BrandingContext';
import { Spinner } from '@/components/ui/spinner';
import { Upload } from 'lucide-react';
import { toast } from 'sonner';

export default function SettingsPage() {
  const { branding, applyTheme } = useBranding();
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState<Partial<BrandingResponse>>({});
  const [logoFile, setLogoFile] = useState<File | null>(null);

  useEffect(() => {
    if (branding) {
      setFormData({
        nom_clinique: branding.nom_clinique,
        couleur_primaire: branding.couleur_primaire,
        couleur_secondaire: branding.couleur_secondaire,
        contenu_landing: branding.contenu_landing,
      });
    }
  }, [branding]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name.startsWith('contenu_')) {
      const key = name.replace('contenu_', '');
      setFormData({
        ...formData,
        contenu_landing: {
          ...formData.contenu_landing,
          [key]: value,
        },
      });
    } else {
      setFormData({
        ...formData,
        [name]: value,
      });
    }
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setLogoFile(e.target.files[0]);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      // Update branding settings
      const response = await settingsApi.updateBranding(formData);
      applyTheme(response.data);
      toast.success('Paramètres sauvegardés');

      // Upload logo if selected
      if (logoFile) {
        try {
          await settingsApi.uploadLogo(logoFile);
          toast.success('Logo téléchargé');
          setLogoFile(null);
        } catch (err: any) {
          const message = err.response?.data?.detail || 'Erreur lors du téléchargement du logo';
          toast.error(message);
        }
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Erreur lors de la sauvegarde';
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (!branding) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-2xl">
        <div>
          <h1 className="text-3xl font-bold">Paramètres</h1>
          <p className="text-muted-foreground mt-1">Configuration du branding et de la clinique</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Informations générales</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="nom_clinique">Nom de la clinique</Label>
              <Input
                id="nom_clinique"
                name="nom_clinique"
                value={formData.nom_clinique || ''}
                onChange={handleInputChange}
                placeholder="Nom de votre clinique"
              />
            </div>

            <div>
              <Label>Logo</Label>
              <div className="flex items-center gap-4">
                {branding.logo_url && (
                  <img src={branding.logo_url} alt="Logo" className="h-16 w-16 object-contain border rounded" />
                )}
                <div className="flex-1">
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoChange}
                    className="cursor-pointer"
                  />
                  <p className="text-xs text-muted-foreground mt-1">PNG, JPG (max 2 Mo)</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Couleurs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="couleur_primaire">Couleur primaire</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="couleur_primaire"
                  name="couleur_primaire"
                  type="color"
                  value={formData.couleur_primaire || '#0066CC'}
                  onChange={handleInputChange}
                  className="w-16 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={formData.couleur_primaire || '#0066CC'}
                  onChange={handleInputChange}
                  name="couleur_primaire"
                  placeholder="#0066CC"
                  className="flex-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="couleur_secondaire">Couleur secondaire</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="couleur_secondaire"
                  name="couleur_secondaire"
                  type="color"
                  value={formData.couleur_secondaire || '#6B7280'}
                  onChange={handleInputChange}
                  className="w-16 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={formData.couleur_secondaire || '#6B7280'}
                  onChange={handleInputChange}
                  name="couleur_secondaire"
                  placeholder="#6B7280"
                  className="flex-1"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contenu de la landing page</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="contenu_titre">Titre</Label>
              <Input
                id="contenu_titre"
                name="contenu_titre"
                value={formData.contenu_landing?.titre || ''}
                onChange={handleInputChange}
                placeholder="Titre de votre clinique"
              />
            </div>

            <div>
              <Label htmlFor="contenu_sous_titre">Sous-titre</Label>
              <Input
                id="contenu_sous_titre"
                name="contenu_sous_titre"
                value={formData.contenu_landing?.sous_titre || ''}
                onChange={handleInputChange}
                placeholder="Sous-titre"
              />
            </div>

            <div>
              <Label htmlFor="contenu_adresse">Adresse</Label>
              <Input
                id="contenu_adresse"
                name="contenu_adresse"
                value={formData.contenu_landing?.adresse || ''}
                onChange={handleInputChange}
                placeholder="Adresse de la clinique"
              />
            </div>

            <div>
              <Label htmlFor="contenu_telephone">Téléphone</Label>
              <Input
                id="contenu_telephone"
                name="contenu_telephone"
                value={formData.contenu_landing?.telephone || ''}
                onChange={handleInputChange}
                placeholder="Numéro de téléphone"
              />
            </div>

            <div>
              <Label htmlFor="contenu_horaires">Horaires</Label>
              <Textarea
                id="contenu_horaires"
                name="contenu_horaires"
                value={formData.contenu_landing?.horaires || ''}
                onChange={handleInputChange}
                placeholder="Horaires d'ouverture"
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Sauvegarde...' : 'Sauvegarder'}
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
