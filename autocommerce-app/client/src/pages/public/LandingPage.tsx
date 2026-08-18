import React, { useEffect, useMemo, useState } from 'react';
import { useBranding } from '@/contexts/BrandingContext';
import {
  publicApi,
  type PublicActe,
  type PublicDisponibilite,
  type PublicPraticien,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { Calendar, Phone, MapPin, Clock, Stethoscope, UserRound } from 'lucide-react';
import { toast } from 'sonner';

const todayLocalDate = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export default function LandingPage() {
  const { branding } = useBranding();

  const [isBootstrapLoading, setIsBootstrapLoading] = useState(true);
  const [isSlotsLoading, setIsSlotsLoading] = useState(false);
  const [praticiens, setPraticiens] = useState<PublicPraticien[]>([]);
  const [actes, setActes] = useState<PublicActe[]>([]);
  const [availabilities, setAvailabilities] = useState<PublicDisponibilite[]>([]);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    nom: '',
    prenom: '',
    telephone: '',
    praticien_id: '',
    acte_id: '',
    date: todayLocalDate(),
    date_heure: '',
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setIsBootstrapLoading(true);
        const [praticiensResponse, actesResponse] = await Promise.all([
          publicApi.getPraticiens(),
          publicApi.getActes(),
        ]);

        setPraticiens(praticiensResponse.data);
        setActes(actesResponse.data);
        setBootstrapError(null);
      } catch (err) {
        console.error('Failed to bootstrap landing page:', err);
        setBootstrapError('Le module de réservation est temporairement indisponible.');
      } finally {
        setIsBootstrapLoading(false);
      }
    };

    bootstrap();
  }, []);

  useEffect(() => {
    const loadDisponibilites = async () => {
      if (!formData.praticien_id || !formData.date) {
        setAvailabilities([]);
        setFormData((current) => ({ ...current, date_heure: '' }));
        return;
      }

      try {
        setIsSlotsLoading(true);
        const response = await publicApi.getDisponibilites(Number(formData.praticien_id), {
          date: formData.date,
          acte_id: formData.acte_id ? Number(formData.acte_id) : undefined,
        });
        setAvailabilities(response.data.creneaux || []);

        setFormData((current) => {
          const stillExists = (response.data.creneaux || []).some(
            (slot) => slot.datetime === current.date_heure
          );
          return stillExists ? current : { ...current, date_heure: '' };
        });
      } catch (err: any) {
        console.error('Failed to load availabilities:', err);
        setAvailabilities([]);
        setFormData((current) => ({ ...current, date_heure: '' }));
        const message = err.response?.data?.detail || 'Impossible de charger les disponibilités';
        toast.error(message);
      } finally {
        setIsSlotsLoading(false);
      }
    };

    loadDisponibilites();
  }, [formData.praticien_id, formData.acte_id, formData.date]);

  const featuredServices = useMemo(() => {
    const fromBranding = branding?.contenu_landing?.services_mis_en_avant || [];
    if (fromBranding.length > 0) return fromBranding;
    return actes.slice(0, 3).map((acte) => acte.nom);
  }, [branding?.contenu_landing?.services_mis_en_avant, actes]);

  const selectedActe = useMemo(
    () => actes.find((acte) => acte.id === Number(formData.acte_id)),
    [actes, formData.acte_id]
  );

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((current) => ({
      ...current,
      [name]: value,
      ...(name === 'praticien_id' || name === 'acte_id' || name === 'date'
        ? { date_heure: '' }
        : {}),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.telephone.match(/^\+?[0-9 ]{8,15}$/)) {
      toast.error('Format de téléphone invalide');
      return;
    }

    if (!formData.date_heure) {
      toast.error('Veuillez sélectionner un créneau disponible');
      return;
    }

    try {
      setIsSubmitting(true);

      await publicApi.reserveRdv({
        nom: formData.nom,
        prenom: formData.prenom,
        telephone: formData.telephone,
        praticien_id: Number(formData.praticien_id),
        acte_id: Number(formData.acte_id),
        date_heure: formData.date_heure,
      });

      toast.success('Rendez-vous réservé avec succès');
      setFormData({
        nom: '',
        prenom: '',
        telephone: '',
        praticien_id: '',
        acte_id: '',
        date: todayLocalDate(),
        date_heure: '',
      });
      setAvailabilities([]);
    } catch (err: any) {
      if (err.response?.status === 429) {
        toast.error('Trop de tentatives. Réessayez dans une minute.');
      } else {
        const message = err.response?.data?.detail || 'Erreur lors de la réservation';
        toast.error(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f3ee] text-[#172126]">
      <header className="absolute inset-x-0 top-0 z-50 border-b border-white/20 bg-[#172126]/35 text-white backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5 lg:px-8">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 items-center justify-center rounded-full border border-[#d7b77a]/60 bg-[#d7b77a]/15 text-[#f4d99f]">
              {branding?.logo_url ? (
                <img src={branding.logo_url} alt="Logo" className="h-8 w-8 object-contain" />
              ) : (
                <Stethoscope className="h-5 w-5" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.28em] text-[#f4d99f]">Médecine esthétique</p>
              <h1 className="truncate text-lg font-semibold tracking-tight">
              {branding?.nom_clinique || 'Clinique'}
            </h1>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <LanguageSwitcher />
            <a href="/login" className="hidden rounded-full border border-white/30 px-4 py-2 text-xs font-medium text-white transition hover:border-[#f4d99f] hover:text-[#f4d99f] sm:inline-flex">
              Accès professionnel
            </a>
          </div>
        </div>
      </header>

      <section
        className="relative min-h-[760px] overflow-hidden px-5 pb-16 pt-36 sm:px-8 sm:pb-20 sm:pt-44 lg:px-12"
        style={{
          backgroundImage: 'linear-gradient(120deg, #172126 0%, #344b4d 48%, #8da7a0 100%), radial-gradient(circle at 78% 20%, rgba(244,217,159,0.24), transparent 28%)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-[#101d21]/90 via-[#172126]/65 to-[#172126]/25"
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
          <div className="max-w-2xl">
            <div className="mb-6 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.24em] text-[#f4d99f]">
              <span className="h-px w-10 bg-[#d7b77a]" />
              Beauté naturelle, expertise médicale
            </div>
            <h2 className="max-w-xl text-5xl font-semibold leading-[1.04] tracking-[-0.04em] text-white drop-shadow-sm sm:text-6xl lg:text-7xl">
              {branding?.contenu_landing?.titre || 'Bienvenue'}
            </h2>
            <p className="mb-9 max-w-lg text-lg leading-8 text-white/80 sm:text-xl">
              {branding?.contenu_landing?.sous_titre || 'Votre clinique esthétique de confiance'}
            </p>

            {featuredServices.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-white/65">
                  Services mis en avant
                </p>
                <div className="flex flex-wrap gap-2">
                  {featuredServices.map((service) => (
                    <span
                      key={service}
                      className="inline-flex items-center rounded-full border border-white/30 bg-white/10 px-4 py-2 text-sm text-white shadow-sm backdrop-blur-md"
                    >
                      <Stethoscope className="w-4 h-4 mr-2 text-primary" />
                      {service}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <Card className="border-white/70 bg-[#fbfaf7]/95 shadow-[0_30px_90px_rgba(10,28,32,0.28)] backdrop-blur-xl">
            <CardHeader className="border-b border-[#172126]/10 px-6 pb-5 pt-6 sm:px-8">
              <CardTitle className="flex items-center gap-3 text-lg tracking-tight text-[#172126]">
                <Calendar className="w-5 h-5" />
                Réserver un rendez-vous
              </CardTitle>
            </CardHeader>
            <CardContent className="px-6 pb-7 pt-6 sm:px-8">
              {isBootstrapLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner className="h-5 w-5" />
                </div>
              ) : bootstrapError ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  {bootstrapError} Veuillez contacter la clinique pour prendre rendez-vous.
                </div>
              ) : praticiens.length === 0 || actes.length === 0 ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  Les disponibilités de réservation seront ouvertes après le paramétrage des praticiens et des prestations.
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="prenom">Prénom</Label>
                      <Input id="prenom" name="prenom" value={formData.prenom} onChange={handleInputChange} required />
                    </div>
                    <div>
                      <Label htmlFor="nom">Nom</Label>
                      <Input id="nom" name="nom" value={formData.nom} onChange={handleInputChange} required />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="telephone">Téléphone</Label>
                    <Input
                      id="telephone"
                      name="telephone"
                      type="tel"
                      value={formData.telephone}
                      onChange={handleInputChange}
                      placeholder="+216 XX XXX XXX"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">Format international ou local, 8 chiffres minimum</p>
                  </div>

                  <div>
                    <Label htmlFor="praticien_id">Praticien</Label>
                    <select
                      id="praticien_id"
                      name="praticien_id"
                      value={formData.praticien_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">Sélectionner un praticien</option>
                      {praticiens.map((praticien) => (
                        <option key={praticien.id} value={praticien.id}>
                          {praticien.nom_complet}
                          {praticien.specialite ? ` — ${praticien.specialite}` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="acte_id">Acte</Label>
                    <select
                      id="acte_id"
                      name="acte_id"
                      value={formData.acte_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">Sélectionner un acte</option>
                      {actes.map((acte) => (
                        <option key={acte.id} value={acte.id}>
                          {acte.nom}
                          {acte.duree_minutes ? ` — ${acte.duree_minutes} min` : ''}
                        </option>
                      ))}
                    </select>
                    {selectedActe?.description && (
                      <p className="text-xs text-muted-foreground mt-1">{selectedActe.description}</p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="date">Date souhaitée</Label>
                    <Input
                      id="date"
                      name="date"
                      type="date"
                      min={todayLocalDate()}
                      value={formData.date}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="date_heure">Créneau disponible</Label>
                    <select
                      id="date_heure"
                      name="date_heure"
                      value={formData.date_heure}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                      disabled={!formData.praticien_id || isSlotsLoading}
                    >
                      <option value="">
                        {isSlotsLoading
                          ? 'Chargement des créneaux...'
                          : 'Sélectionner un créneau'}
                      </option>
                      {availabilities.map((slot) => (
                        <option key={slot.datetime} value={slot.datetime}>
                          {slot.heure}
                        </option>
                      ))}
                    </select>
                    {isSlotsLoading && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                        <Spinner className="h-3.5 w-3.5" />
                        Chargement des disponibilités
                      </div>
                    )}
                    {!isSlotsLoading && formData.praticien_id && availabilities.length === 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Aucun créneau disponible pour cette date.
                      </p>
                    )}
                  </div>

                  <Button type="submit" className="w-full" disabled={isSubmitting || isBootstrapLoading}>
                    {isSubmitting ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        Réservation en cours...
                      </>
                    ) : (
                      'Réserver'
                    )}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="border-y border-[#172126]/10 bg-[#fbfaf7] px-5 py-10 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 md:grid-cols-3">
          {branding?.contenu_landing?.adresse && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Adresse</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-line">
                      {branding.contenu_landing.adresse}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {branding?.contenu_landing?.telephone && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <Phone className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Téléphone</p>
                    <a href={`tel:${branding.contenu_landing.telephone}`} className="text-sm text-primary hover:underline">
                      {branding.contenu_landing.telephone}
                    </a>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {branding?.contenu_landing?.horaires && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <Clock className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Horaires</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-line">
                      {branding.contenu_landing.horaires}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      {praticiens.length > 0 && (
        <section className="bg-[#f5f3ee] px-5 py-16 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-7xl">
            <div className="mb-6">
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[#b0884b]">Une équipe dédiée</p>
              <h3 className="text-3xl font-semibold tracking-tight text-[#172126]">Nos praticiens</h3>
              <p className="mt-2 max-w-xl text-[#172126]/65">Des professionnels sélectionnés pour une prise en charge précise, douce et confidentielle.</p>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {praticiens.map((praticien) => (
                <Card key={praticien.id} className="border-[#172126]/10 bg-[#fbfaf7] shadow-[0_12px_35px_rgba(23,33,38,0.06)] transition hover:-translate-y-1 hover:shadow-[0_18px_45px_rgba(23,33,38,0.12)]">
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                      <UserRound className="w-5 h-5 text-primary mt-1" />
                      <div>
                        <p className="font-semibold">{praticien.nom_complet}</p>
                        {praticien.specialite && (
                          <p className="text-sm text-muted-foreground">{praticien.specialite}</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      <footer className="border-t border-[#172126]/10 bg-[#172126] px-5 py-9 text-white/65 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl text-center text-sm">
          <p>&copy; {new Date().getFullYear()} {branding?.nom_clinique || 'Clinique'}. Tous droits réservés.</p>
        </div>
      </footer>
    </div>
  );
}
