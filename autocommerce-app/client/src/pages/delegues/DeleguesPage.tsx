import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Beaker, UserCheck, Calendar, Package } from 'lucide-react';
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

export default function DeleguesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [labos, setLabos] = useState<any[]>([]);
  const [visites, setVisites] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [labosRes, visitesRes] = await Promise.all([
        api.get('/delegues/labos'),
        api.get('/delegues/visites')
      ]);
      setLabos(labosRes.data);
      setVisites(visitesRes.data);
    } catch (err: any) {
      toast.error('Erreur lors du chargement des données délégués');
    } finally {
      setIsLoading(false);
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
        <div>
          <h1 className="text-3xl font-bold">Délégués & Labos</h1>
          <p className="text-muted-foreground mt-1">Gestion des relations laboratoires et échantillons médicaux</p>
        </div>

        <Tabs defaultValue="visites">
          <TabsList>
            <TabsTrigger value="visites"><Calendar className="w-4 h-4 mr-2" /> Visites & Dotations</TabsTrigger>
            <TabsTrigger value="labos"><Beaker className="w-4 h-4 mr-2" /> Laboratoires Partenaires</TabsTrigger>
          </TabsList>

          <TabsContent value="visites" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Historique des Visites</CardTitle>
                <Button size="sm"><Calendar className="w-4 h-4 mr-2" /> Nouvelle Visite</Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Délégué</TableHead>
                      <TableHead>Objet</TableHead>
                      <TableHead>Échantillons</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visites.length === 0 ? (
                      <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">Aucune visite enregistrée</TableCell></TableRow>
                    ) : (
                      visites.map((v) => (
                        <TableRow key={v.id}>
                          <TableCell>{new Date(v.date).toLocaleDateString('fr-FR')}</TableCell>
                          <TableCell className="font-medium">{v.delegue}</TableCell>
                          <TableCell>{v.objet}</TableCell>
                          <TableCell>
                            {v.echantillons ? (
                              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">
                                <Package className="w-3 h-3 inline mr-1" /> Reçus
                              </span>
                            ) : '—'}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="labos" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Laboratoires</CardTitle>
                <Button size="sm"><Beaker className="w-4 h-4 mr-2" /> Ajouter Labo</Button>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {labos.map((l) => (
                    <Card key={l.id} className="border-l-4 border-l-blue-500">
                      <CardContent className="pt-6">
                        <div className="font-bold text-lg">{l.nom}</div>
                        <div className="text-sm text-muted-foreground mt-1">Contact: {l.contact || 'Non spécifié'}</div>
                        <Button variant="ghost" size="sm" className="mt-4 w-full border">Voir Délégués</Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
