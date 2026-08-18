import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/contexts/AuthContext';

interface Commission {
  id: number;
  commercial_id: number;
  commercial_nom: string;
  montant: number;
  statut: 'en_attente' | 'validation_partielle' | 'validee' | 'payee';
  validateur_1_id?: number;
  validateur_1_nom?: string;
  date_creation: string;
}

export default function CommissionsPage() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [validatingId, setValidatingId] = useState<number | null>(null);

  useEffect(() => {
    loadCommissions();
  }, []);

  const loadCommissions = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/commissions');
      // Le backend renvoie un tableau brut, pas { commissions: [...] }
      setCommissions(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      console.error('Failed to load commissions:', err);
      toast.error('Erreur lors du chargement des commissions');
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidate = async (commission: Commission) => {
    try {
      setValidatingId(commission.id);
      await api.patch(`/commissions/${commission.id}/valider`);
      toast.success('Commission validée');
      loadCommissions();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Erreur lors de la validation';
      toast.error(message);
    } finally {
      setValidatingId(null);
    }
  };

  const handlePay = async (commission: Commission) => {
    try {
      setValidatingId(commission.id);
      await api.post(`/commissions/${commission.id}/payer`, { date_paiement: new Date().toISOString().split('T')[0] });
      toast.success('Commission marquée comme payée');
      loadCommissions();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors du paiement');
    } finally {
      setValidatingId(null);
    }
  };

  const canPay = ['directrice', 'admin'].includes(user?.role || '');

  const canValidate = (commission: Commission) => {
    // For partial validation, only the first validator can validate again
    if (commission.statut === 'validation_partielle') {
      return commission.validateur_1_id !== user?.id;
    }
    // For pending, anyone can validate
    return commission.statut === 'en_attente';
  };

  const getStatusColor = (statut: string) => {
    switch (statut) {
      case 'en_attente':
        return 'bg-yellow-100 text-yellow-800';
      case 'validation_partielle':
        return 'bg-blue-100 text-blue-800';
      case 'validee':
        return 'bg-green-100 text-green-800';
      case 'payee':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (statut: string) => {
    switch (statut) {
      case 'en_attente':
        return <Clock className="w-4 h-4" />;
      case 'validation_partielle':
        return <AlertCircle className="w-4 h-4" />;
      case 'validee':
        return <CheckCircle className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const getStatusLabel = (statut: string) => {
    switch (statut) {
      case 'en_attente':
        return 'En attente';
      case 'validation_partielle':
        return 'Validation partielle';
      case 'validee':
        return 'Validée';
      case 'payee':
        return 'Payée';
      default:
        return statut;
    }
  };

  const needsDoubleValidation = (montant: number) => montant > 500;

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
        <div>
          <h1 className="text-3xl font-bold">Commissions</h1>
          <p className="text-muted-foreground mt-1">Gestion des commissions commerciales</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Flux de validation</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>• Commissions ≤ 500 DT : validation directe en un clic</p>
            <p>• Commissions &gt; 500 DT : validation en deux étapes par deux personnes différentes</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {commissions.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Aucune commission</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Commercial</TableHead>
                      <TableHead>Montant</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead>Validateur 1</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {commissions.map((commission) => (
                      <TableRow key={commission.id}>
                        <TableCell className="font-medium">{commission.commercial_nom}</TableCell>
                        <TableCell>
                          <span className={needsDoubleValidation(commission.montant) ? 'font-bold text-orange-600' : ''}>
                            {commission.montant} DT
                          </span>
                          {needsDoubleValidation(commission.montant) && (
                            <span className="ml-2 text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded">
                              Double validation
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(commission.statut)}
                            <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusColor(commission.statut)}`}>
                              {getStatusLabel(commission.statut)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {commission.validateur_1_nom ? (
                            <span>{commission.validateur_1_nom}</span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(commission.date_creation).toLocaleDateString('fr-FR')}
                        </TableCell>
                        <TableCell>
                          {canValidate(commission) ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleValidate(commission)}
                              disabled={validatingId === commission.id}
                            >
                              {validatingId === commission.id ? 'Validation...' : 'Valider'}
                            </Button>
                          ) : commission.statut === 'validee' && canPay ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePay(commission)}
                              disabled={validatingId === commission.id}
                            >
                              {validatingId === commission.id ? 'Paiement...' : 'Payer'}
                            </Button>
                          ) : (
                            <Button variant="ghost" size="sm" disabled>
                              {commission.statut === 'payee' ? 'Payée' : 'Validée'}
                            </Button>
                          )}
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
    </DashboardLayout>
  );
}
