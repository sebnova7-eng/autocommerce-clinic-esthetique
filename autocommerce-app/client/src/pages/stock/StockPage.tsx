import React, { useState, useEffect, useRef } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api, PublicPraticien } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { Spinner } from '@/components/ui/spinner';
import { AlertCircle, Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ConsommablesList } from '@/components/stock/ConsommablesList';
import { ConsommableForm } from '@/components/stock/ConsommableForm';
import { BarcodeCameraScanner } from '@/components/stock/BarcodeCameraScanner';

interface StockProduct {
  produit_id: number;
  nom: string;
  categorie: string;
  stock_total: number;
  unite: string;
  stock_minimum: number;
  nb_lots_actifs: number;
  statut: 'rupture' | 'alerte' | 'ok';
}

interface Alert {
  produit: string;
  lot: string;
  message: string;
}

export default function StockPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [stockData, setStockData] = useState<{ produits: StockProduct[] } | null>(null);
  const [alertes, setAlertes] = useState({ rouge: [] as Alert[], orange: [] as Alert[] });
  const [scanValue, setScanValue] = useState('');
  const [addLotOpen, setAddLotOpen] = useState(false);
  const [addConsommableOpen, setAddConsommableOpen] = useState(false);
  const [injectionDialogOpen, setInjectionDialogOpen] = useState(false);
  const [scannedLot, setScannedLot] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('injectables');
  const hiddenInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadStockData();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (hiddenInputRef.current && document.activeElement !== hiddenInputRef.current) {
        hiddenInputRef.current.focus();
      }
    }, 500);
    return () => clearInterval(interval);
  }, []);

  const loadStockData = async () => {
    try {
      setIsLoading(true);
      const [stockRes, alertesRes] = await Promise.all([
        api.get('/injectables/stock'),
        api.get('/injectables/alertes'),
      ]);
      setStockData(stockRes.data);
      setAlertes(alertesRes.data || { rouge: [], orange: [] });
    } catch (err: any) {
      console.error('Failed to load stock:', err);
      toast.error('Erreur lors du chargement du stock');
    } finally {
      setIsLoading(false);
    }
  };

  const handleScan = async (code: string) => {
    try {
      const response = await api.post('/injectables/scan', { code });
      setScannedLot({ ...response.data, code });
      setInjectionDialogOpen(true);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Lot non trouvé');
    }
  };

  const getStatusColor = (statut: string) => {
    switch (statut) {
      case 'rupture':
        return 'bg-red-100 text-red-800';
      case 'alerte':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-green-100 text-green-800';
    }
  };

  const getStatusLabel = (statut: string) => {
    switch (statut) {
      case 'rupture':
        return 'RUPTURE';
      case 'alerte':
        return 'ALERTE';
      default:
        return 'OK';
    }
  };

  const totalAlertesCritiques = alertes.rouge.length + alertes.orange.length;

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
            <h1 className="text-3xl font-bold">Gestion des Stocks</h1>
            <p className="text-muted-foreground mt-1">Suivi des injectables et consommables</p>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="injectables">Injectables</TabsTrigger>
            <TabsTrigger value="consommables">Consommables</TabsTrigger>
          </TabsList>

          <TabsContent value="injectables" className="space-y-6">
            <div className="flex justify-end">
              <Button onClick={() => setAddLotOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Ajouter un lot
              </Button>
            </div>

        {totalAlertesCritiques > 0 && (
          <Card className="border-destructive bg-destructive/5">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <span className="font-semibold text-destructive">
                  {alertes.rouge.length} alerte(s) rouge(s) — {alertes.orange.length} alerte(s) orange(s)
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Scan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              ref={hiddenInputRef}
              type="text"
              className="absolute opacity-0 w-1 h-1"
              onChange={(e) => {
                const value = e.target.value;
                if (value.length >= 3) {
                  handleScan(value);
                  setScanValue('');
                  e.target.value = '';
                }
              }}
              autoFocus
            />
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1">
                <BarcodeCameraScanner
                  onDetected={(code) => handleScan(code)}
                  compact
                />
              </div>
              <Input
                placeholder="Saisie manuelle..."
                value={scanValue}
                onChange={(e) => setScanValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && scanValue.length >= 3) {
                    handleScan(scanValue);
                    setScanValue('');
                  }
                }}
                className="sm:max-w-xs sm:self-start"
              />
            </div>
          </CardContent>
        </Card>

            <Card>
              <CardHeader>
                <CardTitle>Stock par produit</CardTitle>
              </CardHeader>
              <CardContent>
                {stockData?.produits ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Produit</TableHead>
                          <TableHead>Catégorie</TableHead>
                          <TableHead>Stock</TableHead>
                          <TableHead>Minimum</TableHead>
                          <TableHead>Lots</TableHead>
                          <TableHead>Statut</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {stockData.produits.map((p) => (
                          <TableRow key={p.produit_id}>
                            <TableCell className="font-medium">{p.nom}</TableCell>
                            <TableCell>{p.categorie}</TableCell>
                            <TableCell>
                              {p.stock_total} {p.unite}
                            </TableCell>
                            <TableCell>{p.stock_minimum}</TableCell>
                            <TableCell>{p.nb_lots_actifs}</TableCell>
                            <TableCell>
                              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusColor(p.statut)}`}>
                                {getStatusLabel(p.statut)}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <p className="text-muted-foreground">Aucun produit trouvé</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="consommables">
            <ConsommablesList onAddClick={() => setAddConsommableOpen(true)} />
          </TabsContent>
        </Tabs>
      </div>

      <AddLotDialog
        open={addLotOpen}
        onOpenChange={setAddLotOpen}
        produits={stockData?.produits || []}
        onCreated={loadStockData}
      />

      <ConsommableForm 
        open={addConsommableOpen}
        onOpenChange={setAddConsommableOpen}
        onCreated={() => {
          // Le composant ConsommablesList se rafraîchira via son propre useEffect ou un signal
          // Pour forcer le rafraîchissement si nécessaire, on pourrait passer une prop key ou un callback
          window.location.reload(); // Solution simple pour garantir le rafraîchissement global
        }}
      />

      <InjectionUsageDialog
        open={injectionDialogOpen}
        onOpenChange={setInjectionDialogOpen}
        lot={scannedLot}
        onSuccess={loadStockData}
      />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────

function InjectionUsageDialog({ open, onOpenChange, lot, onSuccess }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  lot: any;
  onSuccess: () => void;
}) {
  const { user } = useAuth();
  const currentRole = user?.role || '';
  const canChoosePraticien = ['directrice', 'assistante', 'admin'].includes(currentRole);
  const [patients, setPatients] = useState<any[]>([]);
  const [praticiens, setPraticiens] = useState<PublicPraticien[]>([]);
  const [patientSearch, setPatientSearch] = useState('');
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [quantite, setQuantite] = useState('');
  const [dateInjection, setDateInjection] = useState(new Date().toISOString().split('T')[0]);
  const [typeInjection, setTypeInjection] = useState('');
  const [praticienId, setPraticienId] = useState(user?.id?.toString() || '');
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingPatients, setIsLoadingPatients] = useState(false);

  useEffect(() => {
    if (open) {
      setQuantite('');
      setDateInjection(new Date().toISOString().split('T')[0]);
      setTypeInjection('');
      setPraticienId(user?.id?.toString() || '');
      setNotes('');
      setSelectedPatientId('');
      setPatientSearch('');
      setPraticiens([]);
      loadPatients();
      if (canChoosePraticien) {
        loadPraticiens();
      }
    }
  }, [open, lot, user, canChoosePraticien]);

  const loadPatients = async (search = '') => {
    try {
      setIsLoadingPatients(true);
      const res = await api.get(`/patients?search=${search}&limit=10`);
      setPatients(res.data);
    } catch (err) {
      console.error('Failed to load patients:', err);
    } finally {
      setIsLoadingPatients(false);
    }
  };

  const loadPraticiens = async () => {
    try {
      const res = await api.get('/settings/public/praticiens');
      const praticiensList = Array.isArray(res.data) ? res.data : [];
      setPraticiens(praticiensList);
      setPraticienId((current) => {
        if (current && praticiensList.some((p: PublicPraticien) => p.id.toString() === current)) {
          return current;
        }
        return praticiensList[0]?.id?.toString() || '';
      });
    } catch (err) {
      console.error('Failed to load practitioners:', err);
      toast.error('Impossible de charger la liste des praticiens');
    }
  };

  const handleSearchPatient = (e: React.FormEvent) => {
    e.preventDefault();
    loadPatients(patientSearch);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !quantite || !praticienId) {
      toast.error('Merci de remplir les champs obligatoires');
      return;
    }

    setIsSaving(true);
    try {
      await api.post('/injectables/utilisation', {
        lot_id: lot.lot_id,
        code: lot.code || undefined,
        patient_id: Number(selectedPatientId),
        praticien_id: Number(praticienId),
        quantite: Number(quantite),
        unite: lot.unite,
        type_injection: typeInjection || undefined,
        date_injection: dateInjection ? `${dateInjection}T12:00:00` : undefined,
        notes: notes || undefined,
      });
      toast.success('Injection enregistrée');
      onOpenChange(false);
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'enregistrement");
    } finally {
      setIsSaving(false);
    }
  };

  if (!lot) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Enregistrer une injection</DialogTitle>
          <DialogDescription>
            Produit : <span className="font-bold text-foreground">{lot.produit_nom}</span> (Lot: {lot.numero_lot})
            <br />
            Stock disponible : {lot.quantite_restante} {lot.unite}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Patient *</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Rechercher..."
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchPatient(e)}
                />
                <Button type="button" size="icon" variant="outline" onClick={() => loadPatients(patientSearch)}>
                  <Search className="w-4 h-4" />
                </Button>
              </div>
              <select
                className="w-full h-9 px-3 border rounded-md text-sm"
                value={selectedPatientId}
                onChange={(e) => setSelectedPatientId(e.target.value)}
              >
                <option value="">Choisir un patient...</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom} {p.prenom} ({p.telephone})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="type_injection">Type d'injection</Label>
              <select
                id="type_injection"
                className="w-full h-9 px-3 border rounded-md text-sm"
                value={typeInjection}
                onChange={(e) => setTypeInjection(e.target.value)}
              >
                <option value="">Non spécifié</option>
                <option value="Botox">Botox</option>
                <option value="Acide Hyaluronique">Acide Hyaluronique</option>
                <option value="Mésothérapie">Mésothérapie</option>
                <option value="Skinbooster">Skinbooster</option>
                <option value="Autre">Autre</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="quantite">Quantité injectée ({lot.unite}) *</Label>
              <Input
                id="quantite"
                type="number"
                step="0.001"
                placeholder="0.000"
                value={quantite}
                onChange={(e) => setQuantite(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="date_injection">Date de l'injection *</Label>
              <Input
                id="date_injection"
                type="date"
                value={dateInjection}
                onChange={(e) => setDateInjection(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="praticien">Praticien *</Label>
              {canChoosePraticien ? (
                <select
                  id="praticien"
                  className="w-full h-9 px-3 border rounded-md text-sm"
                  value={praticienId}
                  onChange={(e) => setPraticienId(e.target.value)}
                >
                  <option value="">Choisir un praticien...</option>
                  {praticiens.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nom_complet}
                    </option>
                  ))}
                </select>
              ) : (
                <>
                  <Input
                    id="praticien"
                    value={user?.nom ? `${user.prenom} ${user.nom}` : ''}
                    disabled
                  />
                  <input type="hidden" value={praticienId} />
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes / Observations</Label>
            <Input
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes optionnelles..."
            />
          </div>

          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4 mr-2" /> : null}
              Enregistrer l'utilisation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────

function AddLotDialog({ open, onOpenChange, produits, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; produits: StockProduct[]; onCreated: () => void;
}) {
  const [produitId, setProduitId] = useState('');
  const [numeroLot, setNumeroLot] = useState('');
  const [dateExpiration, setDateExpiration] = useState('');
  const [quantiteInitiale, setQuantiteInitiale] = useState('');
  const [fournisseur, setFournisseur] = useState('');
  const [prixAchat, setPrixAchat] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setProduitId(''); setNumeroLot(''); setDateExpiration('');
      setQuantiteInitiale(''); setFournisseur(''); setPrixAchat('');
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!produitId || !numeroLot.trim() || !dateExpiration || !quantiteInitiale) {
      toast.error('Merci de compléter les champs requis');
      return;
    }
    setIsSaving(true);
    try {
      await api.post('/injectables/lots', {
        produit_id: Number(produitId),
        numero_lot: numeroLot.trim(),
        date_expiration: dateExpiration,
        quantite_initiale: quantiteInitiale,
        fournisseur: fournisseur || undefined,
        prix_achat_lot: prixAchat || undefined,
      });
      toast.success('Lot ajouté');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'ajout du lot");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajouter un lot</DialogTitle>
          <DialogDescription>Un QR/code-barres sera généré automatiquement pour ce lot.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="produit">Produit *</Label>
            <select id="produit" value={produitId} onChange={(e) => setProduitId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
              <option value="">Sélectionner</option>
              {produits.map((p) => <option key={p.produit_id} value={p.produit_id}>{p.nom}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="numero_lot">Numéro de lot *</Label>
              <Input id="numero_lot" value={numeroLot} onChange={(e) => setNumeroLot(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="date_expiration">Date d'expiration *</Label>
              <Input id="date_expiration" type="date" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="quantite">Quantité initiale *</Label>
              <Input id="quantite" type="number" step="0.001" value={quantiteInitiale} onChange={(e) => setQuantiteInitiale(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="prix_achat">Prix d'achat (DT)</Label>
              <Input id="prix_achat" type="number" step="0.001" value={prixAchat} onChange={(e) => setPrixAchat(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="fournisseur">Fournisseur</Label>
            <Input id="fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Ajouter'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
