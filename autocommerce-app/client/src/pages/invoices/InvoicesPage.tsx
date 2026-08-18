import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { PatientAutocomplete, type PatientOption } from '@/components/patients/PatientAutocomplete';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Trash2, Scan, Zap, CheckCircle, Download } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface Invoice {
  id: number;
  numero_facture: string;
  patient_id: number;
  total_ttc: number;
  statut: string;
  date_emission: string;
}

interface Expense {
  id: number;
  titre: string;
  fournisseur: string | null;
  montant_ttc: number;
  date_depense: string;
  facture_scan_statut: string;
}

const INVOICE_STATUT: Record<string, { label: string; color: string }> = {
  brouillon: { label: 'Brouillon', color: 'bg-gray-100 text-gray-800' },
  envoyee: { label: 'Envoyée', color: 'bg-yellow-100 text-yellow-800' },
  partiellement_payee: { label: 'Partiellement payée', color: 'bg-orange-100 text-orange-800' },
  payee: { label: 'Payée', color: 'bg-green-100 text-green-800' },
  annulee: { label: 'Annulée', color: 'bg-red-100 text-red-800' },
};

const EXPENSE_STATUT: Record<string, { label: string; color: string }> = {
  en_attente: { label: 'En attente', color: 'bg-yellow-100 text-yellow-800' },
  traitee_ia: { label: 'Traitée (IA)', color: 'bg-blue-100 text-blue-800' },
  validee: { label: 'Validée', color: 'bg-green-100 text-green-800' },
  rejetee: { label: 'Rejetée', color: 'bg-red-100 text-red-800' },
};

export default function InvoicesPage() {
  const { user } = useAuth();
  const canManageInvoices = ['directrice', 'assistante', 'admin'].includes(user?.role || '');
  const canCancelInvoices = ['directrice', 'admin'].includes(user?.role || '');
  const canManageExpenses = ['directrice', 'assistante'].includes(user?.role || '');

  const [isLoading, setIsLoading] = useState(true);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState('invoices');
  const [pendingActs, setPendingActs] = useState<any[]>([]);
  const [createInvoiceOpen, setCreateInvoiceOpen] = useState(false);
  const [billingTarget, setBillingTarget] = useState<any>(null);
  const [payTarget, setPayTarget] = useState<Invoice | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Invoice | null>(null);
  const [scanOpen, setScanOpen] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [invoicesRes, expensesRes, pendingRes, auditRes] = await Promise.allSettled([
        api.get('/factures'),
        api.get('/depenses'),
        api.get('/assistant-ia/pending-billing'),
        api.get('/factures/audit-logs'),
      ]);
      setInvoices(invoicesRes.status === 'fulfilled' && Array.isArray(invoicesRes.value.data) ? invoicesRes.value.data : []);
      setExpenses(expensesRes.status === 'fulfilled' && Array.isArray(expensesRes.value.data) ? expensesRes.value.data : []);
      setPendingActs(pendingRes.status === 'fulfilled' && Array.isArray(pendingRes.value.data) ? pendingRes.value.data : []);
      setAuditLogs(auditRes.status === 'fulfilled' && Array.isArray(auditRes.value.data) ? auditRes.value.data : []);
    } catch (err: any) {
      console.error('Failed to load data:', err);
      toast.error('Erreur lors du chargement');
    } finally {
      setIsLoading(false);
    }
  };

  const handleValiderDepense = async (expense: Expense) => {
    try {
      await api.patch(`/depenses/${expense.id}/valider`, {});
      toast.success('Dépense validée');
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la validation');
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
            <h1 className="text-3xl font-bold">Factures & Dépenses</h1>
            <p className="text-muted-foreground mt-1">Gestion financière</p>
          </div>
          {activeTab === 'invoices' && canManageInvoices && (
            <Button onClick={() => setCreateInvoiceOpen(true)}>
              <Plus className="w-4 h-4 mr-2" /> Nouvelle facture
            </Button>
          )}
          {activeTab === 'expenses' && canManageExpenses && (
            <Button onClick={() => setScanOpen(true)}>
              <Scan className="w-4 h-4 mr-2" /> Scanner une facture
            </Button>
          )}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="invoices">Factures clients</TabsTrigger>
            <TabsTrigger value="pending">Actes à facturer <Badge className="ml-2 bg-purple-500">{pendingActs.length}</Badge></TabsTrigger>
            <TabsTrigger value="expenses">Dépenses & Achats</TabsTrigger>
            <TabsTrigger value="audit">Audit Financier</TabsTrigger>
          </TabsList>

          <TabsContent value="invoices" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {invoices.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucune facture</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Numéro</TableHead>
                          <TableHead>Montant TTC</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Date d'émission</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {invoices.map((invoice) => {
                          const s = INVOICE_STATUT[invoice.statut] || { label: invoice.statut, color: 'bg-gray-100 text-gray-800' };
                          const canPay = canManageInvoices && ['envoyee', 'partiellement_payee', 'brouillon'].includes(invoice.statut);
                          const canCancel = canCancelInvoices && !['payee', 'annulee'].includes(invoice.statut);
                          return (
                            <TableRow key={invoice.id}>
                              <TableCell className="font-medium">{invoice.numero_facture}</TableCell>
                              <TableCell>{invoice.total_ttc} DT</TableCell>
                              <TableCell>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {new Date(invoice.date_emission).toLocaleDateString('fr-FR')}
                              </TableCell>
                              <TableCell className="space-x-2">
                                {canPay && (
                                  <Button variant="outline" size="sm" onClick={() => setPayTarget(invoice)}>Payer</Button>
                                )}
                                {canCancel && (
                                  <Button variant="ghost" size="sm" onClick={() => setCancelTarget(invoice)}>Annuler</Button>
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
          </TabsContent>

          <TabsContent value="pending" className="space-y-4">
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Patient</TableHead>
                      <TableHead>Acte médical</TableHead>
                      <TableHead>Prix base</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingActs.length === 0 ? (
                      <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">Aucun acte en attente de facturation</TableCell></TableRow>
                    ) : (
                      pendingActs.map((act) => (
                        <TableRow key={act.dossier_id}>
                          <TableCell>{new Date(act.date).toLocaleDateString('fr-TN')}</TableCell>
                          <TableCell>
                            <div className="font-medium">{act.patient_nom}</div>
                            <Badge variant="outline" className="text-[10px] uppercase">{act.patient_fidelite}</Badge>
                          </TableCell>
                          <TableCell>
                            {act.actes_details?.map((a: any, i: number) => (
                              <div key={i} className="text-xs">• {a.nom}</div>
                            ))}
                          </TableCell>
                          <TableCell>
                            {act.actes_details?.reduce((acc: number, a: any) => acc + (a.prix || 0), 0).toFixed(3)} DT
                          </TableCell>
                          <TableCell className="text-right">
                            <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => setBillingTarget(act)}>
                              <Zap className="w-3 h-3 mr-1" /> Facturer
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="expenses" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {expenses.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucune dépense</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Titre</TableHead>
                          <TableHead>Fournisseur</TableHead>
                          <TableHead>Montant TTC</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Date</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {expenses.map((expense) => {
                          const s = EXPENSE_STATUT[expense.facture_scan_statut] || { label: expense.facture_scan_statut, color: 'bg-gray-100 text-gray-800' };
                          const canValidate = canManageExpenses && expense.facture_scan_statut !== 'validee';
                          return (
                            <TableRow key={expense.id}>
                              <TableCell className="font-medium">{expense.titre}</TableCell>
                              <TableCell>{expense.fournisseur || '—'}</TableCell>
                              <TableCell>{expense.montant_ttc} DT</TableCell>
                              <TableCell>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {new Date(expense.date_depense).toLocaleDateString('fr-FR')}
                              </TableCell>
                              <TableCell>
                                {canValidate && (
                                  <Button variant="outline" size="sm" onClick={() => handleValiderDepense(expense)}>Valider</Button>
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
          </TabsContent>

          <TabsContent value="audit" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {auditLogs.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucun log d'audit financier</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Action</TableHead>
                          <TableHead>Entité</TableHead>
                          <TableHead>Utilisateur</TableHead>
                          <TableHead>Détails</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {auditLogs.map((log) => (
                          <TableRow key={log.id}>
                            <TableCell className="text-xs">{new Date(log.created_at).toLocaleString('fr-FR')}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className="capitalize">{log.action}</Badge>
                            </TableCell>
                            <TableCell className="text-sm font-medium">{log.entite_type} #{log.entite_id}</TableCell>
                            <TableCell className="text-sm">{log.modifie_par_nom}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {JSON.stringify(log.valeur_apres)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <NewInvoiceDialog open={createInvoiceOpen} onOpenChange={setCreateInvoiceOpen} onCreated={loadData} />
      <PayInvoiceDialog invoice={payTarget} onOpenChange={() => setPayTarget(null)} onPaid={loadData} />
      <CancelInvoiceDialog invoice={cancelTarget} onOpenChange={() => setCancelTarget(null)} onCancelled={loadData} />
      <ScanExpenseDialog open={scanOpen} onOpenChange={setScanOpen} onScanned={loadData} />
      <BillingDialog target={billingTarget} onOpenChange={() => setBillingTarget(null)} onInvoiced={loadData} />
    </DashboardLayout>
  );
}

function BillingDialog({ target, onOpenChange, onInvoiced }: { target: any, onOpenChange: () => void, onInvoiced: () => void }) {
  const [lignes, setLignes] = useState<any[]>([]);
  const [remise, setRemise] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    if (target) {
      setLignes(target.actes_details.map((l: any) => ({ 
        description: l.nom, 
        prix: l.prix, 
        quantite: 1 
      })));
      setRemise(0);
      setResult(null);
    }
  }, [target]);

  const updateLigne = (i: number, field: string, value: any) => {
    setLignes(lignes.map((l, idx) => idx === i ? { ...l, [field]: value } : l));
  };

  const handleGenerate = async () => {
    setIsSaving(true);
    try {
      const res = await api.post('/assistant-ia/generate-invoice', {
        patient_id: target.patient_id,
        dossier_id: target.dossier_id,
        remise_manuelle_pct: remise,
        lignes_ajustees: lignes
      });
      setResult(res.data);
      toast.success('Facture générée avec succès');
    } catch (err) {
      toast.error('Erreur lors de la génération');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDownload = () => {
    if (result?.pdf_url) {
      window.open(result.pdf_url, '_blank');
    }
  };

  if (!target) return null;

  return (
    <Dialog open={!!target} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Finalisation de la facture IA</DialogTitle>
          <DialogDescription>Patient : {target.patient_nom} ({target.patient_fidelite.toUpperCase()})</DialogDescription>
        </DialogHeader>
        {!result ? (
          <div className="space-y-4 py-4">
            <div className="space-y-3">
              <Label>Ajustement des prix par acte</Label>
              {lignes.map((l, i) => (
                <div key={i} className="flex gap-2 items-center bg-gray-50 p-2 rounded">
                  <span className="flex-1 text-sm font-medium">{l.description}</span>
                  <Input 
                    type="number" 
                    step="0.001" 
                    value={l.prix} 
                    onChange={(e) => updateLigne(i, 'prix', Number(e.target.value))}
                    className="w-24 h-8 text-sm"
                  />
                  <span className="text-xs text-muted-foreground">DT</span>
                </div>
              ))}
            </div>
            
            <div className="space-y-2 pt-2 border-t">
              <div className="flex justify-between text-xs text-purple-600 font-semibold">
                <span>Remise fidélité automatique</span>
                <span>Inclus selon statut</span>
              </div>
              <Label htmlFor="remise">Remise manuelle supplémentaire (%)</Label>
              <Input id="remise" type="number" value={remise} onChange={(e) => setRemise(Number(e.target.value))} />
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={onOpenChange}>Annuler</Button>
              <Button onClick={handleGenerate} disabled={isSaving} className="bg-purple-600 hover:bg-purple-700">
                {isSaving ? <Spinner className="h-4 w-4" /> : 'Générer & Valider'}
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-6 py-4 text-center">
            <div className="space-y-2">
              <div className="mx-auto w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                <CheckCircle className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold">Facture {result.numero}</h3>
              <p className="text-2xl font-bold text-primary">{result.total.toFixed(3)} DT</p>
              <p className="text-sm text-muted-foreground">Remise totale appliquée : {result.remise_appliquee}%</p>
            </div>
            <div className="flex flex-col gap-2">
              <Button onClick={handleDownload} className="w-full">
                <Download className="w-4 h-4 mr-2" /> Télécharger le PDF
              </Button>
              <Button variant="outline" onClick={() => { onInvoiced(); onOpenChange(); }} className="w-full">
                Fermer
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────

interface LigneForm { description: string; prix: string; quantite: string }

function NewInvoiceDialog({ open, onOpenChange, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void;
}) {
  const [patientAutocompleteKey, setPatientAutocompleteKey] = useState(0);
  const [selectedPatient, setSelectedPatient] = useState<PatientOption | null>(null);
  const [patientId, setPatientId] = useState('');
  const [lignes, setLignes] = useState<LigneForm[]>([{ description: '', prix: '', quantite: '1' }]);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setPatientId('');
      setSelectedPatient(null);
      setPatientAutocompleteKey((prev) => prev + 1);
      setLignes([{ description: '', prix: '', quantite: '1' }]);
    }
  }, [open]);

  const handlePatientSelect = (patient: PatientOption | null) => {
    setSelectedPatient(patient);
    setPatientId(patient ? String(patient.id) : '');
  };

  const updateLigne = (i: number, field: keyof LigneForm, value: string) => {
    setLignes((prev) => prev.map((l, idx) => idx === i ? { ...l, [field]: value } : l));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId) { toast.error('Sélectionnez un patient'); return; }
    const validLignes = lignes.filter((l) => l.description.trim() && Number(l.prix) > 0);
    if (validLignes.length === 0) { toast.error('Ajoutez au moins une ligne valide'); return; }

    setIsSaving(true);
    try {
      await api.post('/factures', {
        patient_id: Number(patientId),
        actes: validLignes.map((l) => ({
          description: l.description.trim(),
          prix: l.prix,
          quantite: Number(l.quantite) || 1,
        })),
      });
      toast.success('Facture créée');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la création');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle facture</DialogTitle>
          <DialogDescription>Ajoutez le patient et les lignes (actes/produits).</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <PatientAutocomplete
            key={patientAutocompleteKey}
            selectedPatient={selectedPatient}
            onSelect={handlePatientSelect}
          />

          <div className="space-y-2">
            <Label>Lignes</Label>
            {lignes.map((ligne, i) => (
              <div key={i} className="flex gap-2 items-start">
                <Input placeholder="Description" value={ligne.description} onChange={(e) => updateLigne(i, 'description', e.target.value)} className="flex-1" />
                <Input placeholder="Prix" type="number" step="0.001" value={ligne.prix} onChange={(e) => updateLigne(i, 'prix', e.target.value)} className="w-24" />
                <Input placeholder="Qté" type="number" value={ligne.quantite} onChange={(e) => updateLigne(i, 'quantite', e.target.value)} className="w-16" />
                <Button type="button" variant="ghost" size="sm" onClick={() => setLignes((prev) => prev.filter((_, idx) => idx !== i))} disabled={lignes.length === 1}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => setLignes((prev) => [...prev, { description: '', prix: '', quantite: '1' }])}>
              <Plus className="w-4 h-4 mr-1" /> Ajouter une ligne
            </Button>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PayInvoiceDialog({ invoice, onOpenChange, onPaid }: {
  invoice: Invoice | null; onOpenChange: () => void; onPaid: () => void;
}) {
  const [mode, setMode] = useState('especes');
  const [isSaving, setIsSaving] = useState(false);

  const handleConfirm = async () => {
    if (!invoice) return;
    setIsSaving(true);
    try {
      await api.post(`/factures/${invoice.id}/payer`, { mode_paiement: mode });
      toast.success('Facture marquée comme payée');
      onOpenChange();
      onPaid();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors du paiement');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!invoice} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enregistrer le paiement</DialogTitle>
          <DialogDescription>{invoice && `${invoice.numero_facture} — ${invoice.total_ttc} DT`}</DialogDescription>
        </DialogHeader>
        <div>
          <Label htmlFor="mode">Mode de paiement</Label>
          <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
            <option value="especes">Espèces</option>
            <option value="carte">Carte bancaire</option>
            <option value="cheque">Chèque</option>
            <option value="virement">Virement</option>
          </select>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onOpenChange}>Annuler</Button>
          <Button onClick={handleConfirm} disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Confirmer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CancelInvoiceDialog({ invoice, onOpenChange, onCancelled }: {
  invoice: Invoice | null; onOpenChange: () => void; onCancelled: () => void;
}) {
  const [motif, setMotif] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  useEffect(() => setMotif(''), [invoice]);

  const handleConfirm = async () => {
    if (!invoice) return;
    if (motif.trim().length < 3) { toast.error('Merci de préciser un motif'); return; }
    setIsSaving(true);
    try {
      await api.post(`/factures/${invoice.id}/annuler`, { motif: motif.trim() });
      toast.success('Facture annulée');
      onOpenChange();
      onCancelled();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'annulation");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!invoice} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Annuler la facture</DialogTitle>
          <DialogDescription>{invoice?.numero_facture}</DialogDescription>
        </DialogHeader>
        <div>
          <Label htmlFor="motif">Motif *</Label>
          <Textarea id="motif" value={motif} onChange={(e) => setMotif(e.target.value)} rows={3} />
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

function ScanExpenseDialog({ open, onOpenChange, onScanned }: {
  open: boolean; onOpenChange: (v: boolean) => void; onScanned: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [fournisseur, setFournisseur] = useState('');
  const [titre, setTitre] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => { if (open) { setFile(null); setFournisseur(''); setTitre(''); } }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { toast.error('Sélectionnez un fichier'); return; }
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post('/depenses/scan', formData, {
        params: { fournisseur: fournisseur || undefined, titre: titre || undefined },
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Facture envoyée pour extraction automatique');
      onOpenChange(false);
      onScanned();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'envoi");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scanner une facture fournisseur</DialogTitle>
          <DialogDescription>L'extraction des montants se fait automatiquement (IA) après envoi.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="scan-file">Fichier (PDF ou image)</Label>
            <input id="scan-file" type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} className="w-full text-sm" />
          </div>
          <div>
            <Label htmlFor="fournisseur">Fournisseur (optionnel)</Label>
            <Input id="fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="titre">Titre (optionnel)</Label>
            <Input id="titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isUploading}>{isUploading ? <Spinner className="h-4 w-4" /> : 'Envoyer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
