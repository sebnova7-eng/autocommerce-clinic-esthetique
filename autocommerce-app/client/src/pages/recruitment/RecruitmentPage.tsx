import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { ChevronRight, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface Candidate {
  id: number;
  poste: string;
  nom_candidat: string;
  email: string;
  telephone: string | null;
  statut: 'recu' | 'en_etude' | 'entretien' | 'accepte' | 'refuse';
  created_at: string;
}

const NEXT_STATUS: Record<string, string> = {
  recu: 'en_etude',
  en_etude: 'entretien',
  entretien: 'accepte',
};

const STATUT_INFO: Record<string, { label: string; color: string }> = {
  recu: { label: 'Reçu', color: 'bg-blue-100 text-blue-800' },
  en_etude: { label: 'En étude', color: 'bg-yellow-100 text-yellow-800' },
  entretien: { label: 'Entretien', color: 'bg-purple-100 text-purple-800' },
  accepte: { label: 'Accepté', color: 'bg-green-100 text-green-800' },
  refuse: { label: 'Refusé', color: 'bg-red-100 text-red-800' },
};

export default function RecruitmentPage() {
  const { user } = useAuth();
  const canManage = ['directrice', 'assistante', 'admin'].includes(user?.role || '');
  const [isLoading, setIsLoading] = useState(true);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    loadCandidates();
  }, []);

  const loadCandidates = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/recrutement');
      // Le backend renvoie un tableau brut, pas { candidatures: [...] }
      setCandidates(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      console.error('Failed to load candidates:', err);
      toast.error('Erreur lors du chargement des candidatures');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdvance = async (candidate: Candidate) => {
    const next = NEXT_STATUS[candidate.statut];
    if (!next) return;
    try {
      setUpdatingId(candidate.id);
      await api.patch(`/recrutement/${candidate.id}/statut`, { statut: next });
      toast.success('Statut mis à jour');
      loadCandidates();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la mise à jour');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleRefuse = async (candidate: Candidate) => {
    try {
      setUpdatingId(candidate.id);
      await api.patch(`/recrutement/${candidate.id}/statut`, { statut: 'refuse' });
      toast.success('Candidature refusée');
      loadCandidates();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la mise à jour');
    } finally {
      setUpdatingId(null);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96"><Spinner /></div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Recrutement</h1>
            <p className="text-muted-foreground mt-1">Gestion des candidatures</p>
          </div>
          {canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="w-4 h-4 mr-2" /> Nouvelle candidature
            </Button>
          )}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Flux de candidature</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>Reçu → En étude → Entretien → Accepté / Refusé</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {candidates.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Aucune candidature</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Candidat</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Téléphone</TableHead>
                      <TableHead>Poste</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {candidates.map((candidate) => {
                      const s = STATUT_INFO[candidate.statut] || { label: candidate.statut, color: 'bg-gray-100 text-gray-800' };
                      const canAdvance = canManage && !!NEXT_STATUS[candidate.statut];
                      const canRefuse = canManage && candidate.statut !== 'accepte' && candidate.statut !== 'refuse';
                      return (
                        <TableRow key={candidate.id}>
                          <TableCell className="font-medium">{candidate.nom_candidat}</TableCell>
                          <TableCell className="text-sm">{candidate.email}</TableCell>
                          <TableCell className="text-sm">{candidate.telephone || '—'}</TableCell>
                          <TableCell className="text-sm">{candidate.poste}</TableCell>
                          <TableCell>
                            <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(candidate.created_at).toLocaleDateString('fr-FR')}
                          </TableCell>
                          <TableCell className="space-x-2">
                            {canAdvance && (
                              <Button variant="outline" size="sm" onClick={() => handleAdvance(candidate)} disabled={updatingId === candidate.id}>
                                <ChevronRight className="w-4 h-4 mr-1" /> Avancer
                              </Button>
                            )}
                            {canRefuse && (
                              <Button variant="ghost" size="sm" onClick={() => handleRefuse(candidate)} disabled={updatingId === candidate.id}>
                                Refuser
                              </Button>
                            )}
                            {!canAdvance && !canRefuse && (
                              <Button variant="ghost" size="sm" disabled>Terminé</Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <NewCandidateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={loadCandidates} />
    </DashboardLayout>
  );
}

function NewCandidateDialog({ open, onOpenChange, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void;
}) {
  const [poste, setPoste] = useState('');
  const [nomCandidat, setNomCandidat] = useState('');
  const [email, setEmail] = useState('');
  const [telephone, setTelephone] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) { setPoste(''); setNomCandidat(''); setEmail(''); setTelephone(''); }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!poste.trim() || !nomCandidat.trim() || !email.trim()) {
      toast.error('Merci de compléter les champs requis');
      return;
    }
    setIsSaving(true);
    try {
      await api.post('/recrutement', {
        poste: poste.trim(),
        nom_candidat: nomCandidat.trim(),
        email: email.trim(),
        telephone: telephone.trim() || undefined,
      });
      toast.success('Candidature enregistrée');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'enregistrement");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle candidature</DialogTitle>
          <DialogDescription>Enregistrez une candidature reçue (email, dépôt en clinique, etc.).</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="poste">Poste *</Label>
            <Input id="poste" value={poste} onChange={(e) => setPoste(e.target.value)} placeholder="ex : Esthéticienne" />
          </div>
          <div>
            <Label htmlFor="nom_candidat">Nom du candidat *</Label>
            <Input id="nom_candidat" value={nomCandidat} onChange={(e) => setNomCandidat(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="email">Email *</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="telephone">Téléphone</Label>
              <Input id="telephone" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
