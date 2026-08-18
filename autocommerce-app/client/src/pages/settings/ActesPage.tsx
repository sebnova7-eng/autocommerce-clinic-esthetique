import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Edit2, Trash2, Save, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface Acte {
  id: number;
  nom: string;
  categorie: string;
  duree_minutes: number;
  prix_base: number;
  description?: string;
  is_active: boolean;
}

export default function ActesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [actes, setActes] = useState<Acte[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingActe, setEditingActe] = useState<Acte | null>(null);
  const [formData, setFormData] = useState({
    nom: '',
    categorie: '',
    duree_minutes: 30,
    prix_base: 0,
    description: '',
    is_active: true,
  });

  useEffect(() => {
    loadActes();
  }, []);

  const loadActes = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/settings/actes');
      setActes(res.data);
    } catch (err) {
      toast.error('Erreur lors du chargement des actes');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDialog = (acte?: Acte) => {
    if (acte) {
      setEditingActe(acte);
      setFormData({
        nom: acte.nom,
        categorie: acte.categorie,
        duree_minutes: acte.duree_minutes,
        prix_base: acte.prix_base,
        description: acte.description || '',
        is_active: acte.is_active,
      });
    } else {
      setEditingActe(null);
      setFormData({
        nom: '',
        categorie: '',
        duree_minutes: 30,
        prix_base: 0,
        description: '',
        is_active: true,
      });
    }
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingActe) {
        await api.patch(`/settings/actes/${editingActe.id}`, formData);
        toast.success('Acte mis à jour');
      } else {
        await api.post('/settings/actes', formData);
        toast.success('Acte créé');
      }
      setIsDialogOpen(false);
      loadActes();
    } catch (err) {
      toast.error('Erreur lors de la sauvegarde');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">Tarification des Actes</h1>
            <p className="text-muted-foreground mt-1">Gérez le catalogue des soins et leurs prix</p>
          </div>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="w-4 h-4 mr-2" /> Nouvel acte
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex justify-center p-8"><Spinner /></div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Catégorie</TableHead>
                    <TableHead>Durée (min)</TableHead>
                    <TableHead>Prix de base (DT)</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {actes.map((acte) => (
                    <TableRow key={acte.id}>
                      <TableCell className="font-medium">{acte.nom}</TableCell>
                      <TableCell className="capitalize">{acte.categorie}</TableCell>
                      <TableCell>{acte.duree_minutes}</TableCell>
                      <TableCell>{Number(acte.prix_base).toFixed(3)}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${acte.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {acte.is_active ? 'Actif' : 'Inactif'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(acte)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingActe ? 'Modifier l\'acte' : 'Nouvel acte'}</DialogTitle>
            <DialogDescription>Définissez les détails et le tarif de la prestation.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="nom">Nom de l'acte *</Label>
              <Input id="nom" value={formData.nom} onChange={(e) => setFormData({...formData, nom: e.target.value})} placeholder="ex: Lifting visage" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="categorie">Catégorie</Label>
                <Input id="categorie" value={formData.categorie} onChange={(e) => setFormData({...formData, categorie: e.target.value})} placeholder="ex: Chirurgie" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prix">Prix de base (DT)</Label>
                <Input id="prix" type="number" step="0.001" value={formData.prix_base} onChange={(e) => setFormData({...formData, prix_base: Number(e.target.value)})} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Annuler</Button>
            <Button onClick={handleSave}>Sauvegarder</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
