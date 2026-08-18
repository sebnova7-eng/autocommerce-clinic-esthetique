import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Gift, TrendingUp, TrendingDown } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ParrainageSection } from './ParrainageSection';

interface LoyaltyTransaction {
  id: number;
  patient_nom: string;
  type: 'gain' | 'depense';
  points: number;
  motif: string;
  date: string;
}

export default function LoyaltyPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [transactions, setTransactions] = useState<LoyaltyTransaction[]>([]);
  const [totalPoints, setTotalPoints] = useState(0);

  useEffect(() => {
    loadLoyaltyData();
  }, []);

  const loadLoyaltyData = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/fidelite');
      setTransactions(response.data.transactions || []);
      setTotalPoints(response.data.total_points || 0);
    } catch (err: any) {
      console.error('Failed to load loyalty data:', err);
      toast.error('Erreur lors du chargement des données de fidélité');
    } finally {
      setIsLoading(false);
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
        <div>
          <h1 className="text-3xl font-bold">Fidélité & Parrainage</h1>
          <p className="text-muted-foreground mt-1">Gestion du programme de récompenses</p>
        </div>

        <Tabs defaultValue="historique" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="historique">Historique & Points</TabsTrigger>
            <TabsTrigger value="parrainage">Parrainage</TabsTrigger>
          </TabsList>

          <TabsContent value="historique" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gift className="w-5 h-5" />
                  Points totaux
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-primary">{totalPoints} pts</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Historique des transactions</CardTitle>
              </CardHeader>
              <CardContent>
                {transactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucune transaction</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Patient</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Points</TableHead>
                          <TableHead>Motif</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {transactions.map((tx) => (
                          <TableRow key={tx.id}>
                            <TableCell className="font-medium">{tx.patient_nom}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {tx.type === 'gain' ? (
                                  <>
                                    <TrendingUp className="w-4 h-4 text-green-600" />
                                    <span className="text-green-600">Gain</span>
                                  </>
                                ) : (
                                  <>
                                    <TrendingDown className="w-4 h-4 text-red-600" />
                                    <span className="text-red-600">Dépense</span>
                                  </>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="font-semibold">{tx.points} pts</TableCell>
                            <TableCell>{tx.motif}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(tx.date).toLocaleDateString('fr-FR')}
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

          <TabsContent value="parrainage">
            <ParrainageSection patientId={1} />
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
