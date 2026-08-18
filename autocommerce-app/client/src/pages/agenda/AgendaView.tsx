import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, publicApi } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { useAuth } from '@/contexts/AuthContext';
import { Calendar, Plus, Clock, User, Video, ChevronLeft, ChevronRight } from 'lucide-react';
import { Link } from 'wouter';
import { toast } from 'sonner';
import { PatientAutocomplete, type PatientOption } from '@/components/patients/PatientAutocomplete';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

interface Appointment {
  id: number;
  date_heure_debut: string;
  patient_id: number;
  patient_nom: string;
  praticien_id: number;
  praticien_nom: string;
  acte_nom?: string;
  statut: string;
  consentement_manquant: boolean;
}

const STATUT_LABELS: Record<string, { label: string; color: string }> = {
  planifie: { label: 'Planifié', color: 'bg-blue-100 text-blue-800' },
  confirme: { label: 'Confirmé', color: 'bg-green-100 text-green-800' },
  en_cours: { label: 'En cours', color: 'bg-yellow-100 text-yellow-800' },
  termine: { label: 'Terminé', color: 'bg-gray-200 text-gray-800' },
  annule: { label: 'Annulé', color: 'bg-red-100 text-red-800' },
  no_show: { label: 'Absence', color: 'bg-orange-100 text-orange-800' },
};

export default function AgendaView() {
  const { user } = useAuth();
  const canManage = user?.role === 'directrice' || user?.role === 'assistante' || user?.role === 'medecin';
  const canCancel = user?.role === 'directrice' || user?.role === 'assistante';
  const [isLoading, setIsLoading] = useState(true);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [view, setView] = useState<'jour' | 'semaine'>('jour');
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);

  const dateStr = selectedDate;
  
  const getWeekDates = (baseDate: string) => {
    const d = new Date(baseDate);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Lundi
    const monday = new Date(d.setDate(diff));
    return Array.from({ length: 6 }, (_, i) => {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);
      return date.toISOString().split('T')[0];
    });
  };

  const weekDates = getWeekDates(dateStr);

  const selectedDateLabel = (() => {
    if (view === 'jour') {
      const parsed = new Date(`${dateStr}T12:00:00`);
      return parsed.toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
    const first = new Date(`${weekDates[0]}T12:00:00`);
    const last = new Date(`${weekDates[5]}T12:00:00`);
    return `Semaine du ${first.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })} au ${last.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })}`;
  })();

  useEffect(() => {
    loadAppointments();
  }, [dateStr, view]);

  const loadAppointments = async () => {
    try {
      setIsLoading(true);
      const params = view === 'jour' 
        ? { vue: 'jour', date_debut: `${dateStr}T00:00:00`, date_fin: `${dateStr}T23:59:59` }
        : { vue: 'semaine', date_debut: `${weekDates[0]}T00:00:00`, date_fin: `${weekDates[5]}T23:59:59` };
      
      const response = await api.get('/agenda', { params });
      setAppointments(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      toast.error("Erreur lors du chargement");
    } finally {
      setIsLoading(false);
    }
  };

  const navigateDate = (direction: number) => {
    const d = new Date(dateStr);
    if (view === 'jour') d.setDate(d.getDate() + direction);
    else d.setDate(d.getDate() + (direction * 7));
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const handleStatusChange = async (rdv: Appointment, statut: string) => {
    try {
      await api.patch(`/agenda/rdv/${rdv.id}/statut`, { statut });
      toast.success('Statut mis à jour');
      loadAppointments();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la mise à jour');
    }
  };

  if (isLoading) {
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
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Agenda</h1>
            <div className="flex items-center gap-2 mt-1">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(-1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <p className="text-muted-foreground font-medium min-w-[200px] text-center">
                {selectedDateLabel}
              </p>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-muted p-1 rounded-md flex">
              <Button 
                variant={view === 'jour' ? 'secondary' : 'ghost'} 
                size="sm" 
                className="h-8 text-xs"
                onClick={() => setView('jour')}
              >
                Jour
              </Button>
              <Button 
                variant={view === 'semaine' ? 'secondary' : 'ghost'} 
                size="sm" 
                className="h-8 text-xs"
                onClick={() => setView('semaine')}
              >
                Semaine
              </Button>
            </div>
            {canManage && (
              <Button onClick={() => setCreateOpen(true)} className="h-9">
                <Plus className="w-4 h-4 mr-2" />
                Nouveau RDV
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6">
          {view === 'semaine' ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {weekDates.map((date) => {
                const dayRdvs = appointments.filter(a => a.date_heure_debut.startsWith(date));
                const d = new Date(date);
                const isToday = date === new Date().toISOString().split('T')[0];
                return (
                  <div key={date} className={`space-y-3 p-3 rounded-lg border ${isToday ? 'bg-purple-50/50 border-purple-200' : 'bg-card'}`}>
                    <div className="text-center pb-2 border-b">
                      <p className="text-[10px] uppercase text-muted-foreground font-bold">
                        {d.toLocaleDateString('fr-FR', { weekday: 'short' })}
                      </p>
                      <p className={`text-lg font-bold ${isToday ? 'text-purple-700' : ''}`}>
                        {d.getDate()}
                      </p>
                    </div>
                    <div className="space-y-2 min-h-[100px]">
                      {dayRdvs.length === 0 ? (
                        <p className="text-[10px] text-center text-muted-foreground pt-4 italic">Libre</p>
                      ) : (
                        dayRdvs.map(rdv => (
                          <div key={rdv.id} className="p-2 rounded bg-white border text-[10px] shadow-sm">
                            <p className="font-bold">{new Date(rdv.date_heure_debut).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</p>
                            <p className="truncate">{rdv.patient_nom}</p>
                            <p className="text-muted-foreground truncate">{rdv.acte_nom}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-4">
              {appointments.length === 0 ? (
                <Card><CardContent className="pt-6 text-center text-muted-foreground">Aucun RDV</CardContent></Card>
              ) : (
                appointments.map((appointment) => {
              const statutInfo = STATUT_LABELS[appointment.statut] || { label: appointment.statut, color: 'bg-gray-100 text-gray-800' };
              return (
                <Card key={appointment.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Clock className="w-4 h-4 text-muted-foreground" />
                          <span className="font-semibold">
                            {new Date(appointment.date_heure_debut).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${statutInfo.color}`}>
                            {statutInfo.label}
                          </span>
                          {appointment.consentement_manquant && (
                            <span className="inline-block px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">
                              Consentement manquant
                            </span>
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm">{appointment.patient_nom}</span>
                          </div>
                          <p className="text-sm text-muted-foreground">{appointment.acte_nom || 'Acte non spécifié'}</p>
                          <p className="text-xs text-muted-foreground">Praticien: {appointment.praticien_nom}</p>
                          {appointment.statut !== 'annule' && appointment.statut !== 'termine' && (
                            <div className="pt-2">
                              <Link href={`/teleconsultation/${appointment.id}`}>
                                <Button size="sm" variant="outline" className="h-8 text-xs gap-2">
                                  <Video className="w-3.5 h-3.5" />
                                  Démarrer Visio
                                </Button>
                              </Link>
                            </div>
                          )}
                        </div>
                      </div>
                      {canManage && appointment.statut !== 'annule' && (
                        <div className="flex gap-2">
                          <select
                            value={appointment.statut}
                            onChange={(e) => handleStatusChange(appointment, e.target.value)}
                            className="text-sm border rounded-md px-2 py-1"
                          >
                            {Object.entries(STATUT_LABELS).filter(([k]) => k !== 'annule').map(([k, v]) => (
                              <option key={k} value={k}>{v.label}</option>
                            ))}
                          </select>
                          {canCancel && (
                            <Button variant="ghost" size="sm" onClick={() => setCancelTarget(appointment)}>
                              Annuler
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
            </div>
          )}
        </div>
      </div>

      <NewRdvDialog open={createOpen} onOpenChange={setCreateOpen} defaultDate={dateStr} onCreated={loadAppointments} />
      <CancelRdvDialog appointment={cancelTarget} onOpenChange={() => setCancelTarget(null)} onCancelled={loadAppointments} />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────

interface Praticien { id: number; nom: string; prenom: string; specialite?: string | null }
interface Acte { id: number; nom: string; duree_minutes: number }

function NewRdvDialog({ open, onOpenChange, defaultDate, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; defaultDate: string; onCreated: () => void;
}) {
  const [patientAutocompleteKey, setPatientAutocompleteKey] = useState(0);
  const [selectedPatient, setSelectedPatient] = useState<PatientOption | null>(null);
  const [patientId, setPatientId] = useState('');
  const [praticiens, setPraticiens] = useState<Praticien[]>([]);
  const [praticienId, setPraticienId] = useState('');
  const [actes, setActes] = useState<Acte[]>([]);
  const [acteId, setActeId] = useState('');
  const [date, setDate] = useState(defaultDate);
  const [creneaux, setCreneaux] = useState<string[]>([]);
  const [creneau, setCreneau] = useState('');
  const [salle, setSalle] = useState('');
  const [isLoadingCreneaux, setIsLoadingCreneaux] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handlePatientSelect = (patient: PatientOption | null) => {
    setSelectedPatient(patient);
    setPatientId(patient ? String(patient.id) : '');
  };

  useEffect(() => {
    if (open) {
      setSelectedPatient(null); setPatientId('');
      setPatientAutocompleteKey((prev) => prev + 1);
      setPraticienId(''); setActeId(''); setDate(defaultDate);
      setCreneaux([]); setCreneau(''); setSalle('');
      publicApi.getPraticiens().then((r) => setPraticiens(r.data)).catch(() => {});
      publicApi.getActes().then((r) => setActes(r.data)).catch(() => {});
    }
  }, [open, defaultDate]);

  useEffect(() => {
    if (!praticienId || !date) { setCreneaux([]); return; }
    setIsLoadingCreneaux(true);
    setCreneau('');
    api.get(`/agenda/disponibilites/${praticienId}`, { params: { date } })
      .then((r) => setCreneaux(r.data.creneaux || []))
      .catch(() => setCreneaux([]))
      .finally(() => setIsLoadingCreneaux(false));
  }, [praticienId, date]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId || !praticienId || !acteId || !creneau) {
      toast.error('Merci de compléter tous les champs requis');
      return;
    }
    setIsSaving(true);
    try {
      await api.post('/agenda/rdv', {
        patient_id: Number(patientId),
        praticien_id: Number(praticienId),
        acte_id: Number(acteId),
        date_heure: creneau,
        salle: salle || undefined,
      });
      toast.success('Rendez-vous créé');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la création du RDV');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau rendez-vous</DialogTitle>
          <DialogDescription>Recherchez le patient puis choisissez un créneau libre.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <PatientAutocomplete
            key={patientAutocompleteKey}
            selectedPatient={selectedPatient}
            onSelect={handlePatientSelect}
          />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="praticien">Praticien *</Label>
              <select id="praticien" value={praticienId} onChange={(e) => setPraticienId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">Sélectionner</option>
                {praticiens.map((p) => <option key={p.id} value={p.id}>{p.prenom} {p.nom}</option>)}
              </select>
            </div>
            <div>
              <Label htmlFor="acte">Acte *</Label>
              <select id="acte" value={acteId} onChange={(e) => setActeId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">Sélectionner</option>
                {actes.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="rdv-date">Date *</Label>
              <Input id="rdv-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="creneau">Créneau *</Label>
              {isLoadingCreneaux ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-2"><Spinner className="h-4 w-4" /> Recherche...</div>
              ) : (
                <select id="creneau" value={creneau} onChange={(e) => setCreneau(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm" disabled={creneaux.length === 0}>
                  <option value="">{creneaux.length === 0 ? 'Aucun créneau' : 'Sélectionner'}</option>
                  {creneaux.map((c) => (
                    <option key={c} value={c}>{new Date(c).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div>
            <Label htmlFor="salle">Salle</Label>
            <Input id="salle" value={salle} onChange={(e) => setSalle(e.target.value)} placeholder="Optionnel" />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Créer le RDV'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CancelRdvDialog({ appointment, onOpenChange, onCancelled }: {
  appointment: Appointment | null; onOpenChange: () => void; onCancelled: () => void;
}) {
  const [raison, setRaison] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => { setRaison(''); }, [appointment]);

  const handleConfirm = async () => {
    if (!appointment) return;
    if (raison.trim().length < 3) {
      toast.error('Merci de préciser un motif (3 caractères minimum)');
      return;
    }
    setIsSaving(true);
    try {
      await api.delete(`/agenda/rdv/${appointment.id}`, { params: { raison: raison.trim() } });
      toast.success('Rendez-vous annulé');
      onOpenChange();
      onCancelled();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'annulation");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!appointment} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Annuler le rendez-vous</DialogTitle>
          <DialogDescription>
            {appointment && `${appointment.patient_nom} — ${new Date(appointment.date_heure_debut).toLocaleString('fr-FR')}`}
          </DialogDescription>
        </DialogHeader>
        <div>
          <Label htmlFor="raison">Motif de l'annulation *</Label>
          <Textarea id="raison" value={raison} onChange={(e) => setRaison(e.target.value)} rows={3} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onOpenChange}>Retour</Button>
          <Button variant="destructive" onClick={handleConfirm} disabled={isSaving}>
            {isSaving ? <Spinner className="h-4 w-4" /> : "Confirmer l'annulation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
