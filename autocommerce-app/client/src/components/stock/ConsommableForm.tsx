import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

interface ConsommableFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function ConsommableForm({ open, onOpenChange, onCreated }: ConsommableFormProps) {
  const [formData, setFormData] = useState({
    nom: '',
    categorie: '',
    unite: 'pièce',
    stock_actuel: '0',
    seuil_alerte: '5',
    stock_minimum: '2',
    prix_unitaire: '0'
  });
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await api.post('/consommables/create', {
        ...formData,
        stock_actuel: Number(formData.stock_actuel),
        seuil_alerte: Number(formData.seuil_alerte),
        stock_minimum: Number(formData.stock_minimum),
        prix_unitaire: Number(formData.prix_unitaire),
      });
      toast.success('Consommable créé avec succès');
      onCreated();
      onOpenChange(false);
      setFormData({
        nom: '',
        categorie: '',
        unite: 'pièce',
        stock_actuel: '0',
        seuil_alerte: '5',
        stock_minimum: '2',
        prix_unitaire: '0'
      });
    } catch (err) {
      toast.error('Erreur lors de la création du consommable');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Nouveau Consommable</DialogTitle>
          <DialogDescription>
            Ajoutez un nouveau type de consommable au stock.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="nom">Nom *</Label>
            <Input 
              id="nom" 
              value={formData.nom} 
              onChange={(e) => setFormData({...formData, nom: e.target.value})} 
              required 
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="categorie">Catégorie *</Label>
              <Input 
                id="categorie" 
                value={formData.categorie} 
                onChange={(e) => setFormData({...formData, categorie: e.target.value})} 
                placeholder="Ex: Hygiène, Soins..."
                required 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unite">Unité *</Label>
              <select 
                id="unite" 
                value={formData.unite} 
                onChange={(e) => setFormData({...formData, unite: e.target.value})}
                className="w-full h-9 px-3 border rounded-md text-sm"
              >
                <option value="pièce">Pièce</option>
                <option value="boite">Boîte</option>
                <option value="paquet">Paquet</option>
                <option value="rouleau">Rouleau</option>
                <option value="litre">Litre</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="stock">Stock Initial</Label>
              <Input 
                id="stock" 
                type="number" 
                value={formData.stock_actuel} 
                onChange={(e) => setFormData({...formData, stock_actuel: e.target.value})} 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="seuil">Seuil Alerte</Label>
              <Input 
                id="seuil" 
                type="number" 
                value={formData.seuil_alerte} 
                onChange={(e) => setFormData({...formData, seuil_alerte: e.target.value})} 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="min">Minimum</Label>
              <Input 
                id="min" 
                type="number" 
                value={formData.stock_minimum} 
                onChange={(e) => setFormData({...formData, stock_minimum: e.target.value})} 
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="prix">Prix Unitaire (DT)</Label>
            <Input 
              id="prix" 
              type="number" 
              step="0.001" 
              value={formData.prix_unitaire} 
              onChange={(e) => setFormData({...formData, prix_unitaire: e.target.value})} 
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
