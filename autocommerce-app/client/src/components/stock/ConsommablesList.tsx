import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Minus, History, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

export interface Consommable {
  id: number;
  nom: string;
  categorie: string;
  unite: string;
  stock_actuel: number;
  seuil_alerte: number;
  stock_minimum: number;
  prix_unitaire: number;
  is_active: boolean;
}

export function ConsommablesList({ onAddClick }: { onAddClick: () => void }) {
  const [consommables, setConsommables] = useState<Consommable[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mouvementOpen, setMouvementOpen] = useState(false);
  const [selectedConsommable, setSelectedConsommable] = useState<Consommable | null>(null);
  const [mvtType, setMvtType] = useState<'entree' | 'sortie'>('entree');
  const [mvtQuantite, setMvtQuantite] = useState('');
  const [mvtMotif, setMvtMotif] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadConsommables();
  }, []);

  const loadConsommables = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/consommables/list');
      setConsommables(response.data);
    } catch (err) {
      toast.error('Erreur lors du chargement des consommables');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMouvement = (c: Consommable, type: 'entree' | 'sortie') => {
    setSelectedConsommable(c);
    setMvtType(type);
    setMvtQuantite('');
    setMvtMotif('');
    setMouvementOpen(true);
  };

  const submitMouvement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConsommable || !mvtQuantite) return;

    setIsSaving(true);
    try {
      await api.post(`/consommables/${selectedConsommable.id}/mouvement`, {
        type: mvtType,
        quantite: Number(mvtQuantite),
        motif: mvtMotif
      });
      toast.success('Mouvement enregistré');
      setMouvementOpen(false);
      loadConsommables();
    } catch (err) {
      toast.error('Erreur lors de l\'enregistrement du mouvement');
    } finally {
      setIsSaving(false);
    }
  };

  const getStockStatus = (c: Consommable) => {
    if (c.stock_actuel <= c.stock_minimum) return 'text-red-600 font-bold';
    if (c.stock_actuel <= c.seuil_alerte) return 'text-orange-600 font-semibold';
    return '';
  };

  if (isLoading) return <div className="flex justify-center p-8"><Spinner /></div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={onAddClick}>
          <Plus className="w-4 h-4 mr-2" />
          Nouveau consommable
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Stock Actuel</TableHead>
                <TableHead>Unité</TableHead>
                <TableHead>Seuil Alerte</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {consommables.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {c.nom}
                      {c.stock_actuel <= c.seuil_alerte && (
                        <AlertTriangle className={`w-4 h-4 ${c.stock_actuel <= c.stock_minimum ? 'text-red-500' : 'text-orange-500'}`} />
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{c.categorie}</TableCell>
                  <TableCell className={getStockStatus(c)}>
                    {c.stock_actuel}
                  </TableCell>
                  <TableCell>{c.unite}</TableCell>
                  <TableCell>{c.seuil_alerte}</TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'entree')} title="Entrée de stock">
                      <Plus className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'sortie')} title="Sortie de stock">
                      <Minus className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {consommables.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Aucun consommable enregistré
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={mouvementOpen} onOpenChange={setMouvementOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {mvtType === 'entree' ? 'Entrée de stock' : 'Sortie de stock'} : {selectedConsommable?.nom}
            </DialogTitle>
            <DialogDescription>
              Enregistrez un mouvement de stock pour ce consommable.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitMouvement} className="space-y-4">
            <div>
              <Label htmlFor="qte">Quantité ({selectedConsommable?.unite}) *</Label>
              <Input 
                id="qte" 
                type="number" 
                step="0.01" 
                value={mvtQuantite} 
                onChange={(e) => setMvtQuantite(e.target.value)} 
                required 
              />
            </div>
            <div>
              <Label htmlFor="motif">Motif / Commentaire</Label>
              <Input 
                id="motif" 
                value={mvtMotif} 
                onChange={(e) => setMvtMotif(e.target.value)} 
                placeholder="Ex: Réception commande, Utilisation soin..."
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setMouvementOpen(false)}>Annuler</Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
