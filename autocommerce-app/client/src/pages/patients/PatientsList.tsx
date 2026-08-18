import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Search, User, Phone, ShieldOff, Pencil, Eye } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { useLocation } from 'wouter';
import { PatientFormDialog, type Patient } from '@/components/patients/PatientFormDialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function PatientsList() {
  const { user } = useAuth();
  const [, setLocation] = useLocation();
  const canAnonymize = user?.role === 'directrice' || user?.role === 'admin';
  const [isLoading, setIsLoading] = useState(true);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredPatients, setFilteredPatients] = useState<Patient[]>([]);
  const [anonymizingId, setAnonymizingId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null);

  useEffect(() => {
    loadPatients();
  }, []);

  useEffect(() => {
    const filtered = patients.filter(
      (p) =>
        p.nom.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.prenom.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.telephone.includes(searchQuery)
    );
    setFilteredPatients(filtered);
  }, [searchQuery, patients]);

  const loadPatients = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/patients');
      setPatients(Array.isArray(response.data) ? response.data : response.data.patients || []);
    } catch (err: any) {
      console.error('Failed to load patients:', err);
      // Ne jamais conserver des données cliniques d’une session/clinique précédente
      // lorsqu’un rechargement privé est refusé ou échoue.
      setPatients([]);
      toast.error('Erreur lors du chargement des patients');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnonymize = async (patient: Patient) => {
    try {
      setAnonymizingId(patient.id);
      await api.delete(`/patients/${patient.id}/rgpd`);
      toast.success('Patient anonymisé');
      loadPatients();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'anonymisation");
    } finally {
      setAnonymizingId(null);
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Patients</h1>
            <p className="text-muted-foreground mt-1">{patients.length} patient(s) enregistré(s)</p>
          </div>
          <Button onClick={() => { setEditingPatient(null); setFormOpen(true); }}>
            <Plus className="w-4 h-4 mr-2" />
            Nouveau patient
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Rechercher</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom, prénom ou téléphone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {filteredPatients.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Aucun patient trouvé</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nom</TableHead>
                      <TableHead>Prénom</TableHead>
                      <TableHead>Téléphone</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Inscription</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPatients.map((patient) => (
                      <TableRow key={patient.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">{patient.nom}</TableCell>
                        <TableCell>{patient.prenom}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Phone className="w-4 h-4 text-muted-foreground" />
                            {patient.telephone}
                          </div>
                        </TableCell>
                        <TableCell>{patient.email || '-'}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {patient.date_inscription
                            ? new Date(patient.date_inscription).toLocaleDateString('fr-FR')
                            : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setLocation(`/patients/${patient.id}`)}
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              Voir
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => { setEditingPatient(patient); setFormOpen(true); }}
                            >
                              <Pencil className="w-4 h-4 mr-1" />
                              Éditer
                            </Button>
                            {canAnonymize && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-destructive hover:text-destructive"
                                    disabled={anonymizingId === patient.id}
                                  >
                                    <ShieldOff className="w-4 h-4 mr-1" />
                                    Anonymiser
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Anonymiser ce patient ?</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      Cette action est irréversible. Toutes les données
                                      identifiantes de {patient.prenom} {patient.nom} seront
                                      définitivement supprimées, conformément au RGPD.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Annuler</AlertDialogCancel>
                                    <AlertDialogAction
                                      onClick={() => handleAnonymize(patient)}
                                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    >
                                      Confirmer l'anonymisation
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <PatientFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        patient={editingPatient}
        onSaved={loadPatients}
      />
    </DashboardLayout>
  );
}
