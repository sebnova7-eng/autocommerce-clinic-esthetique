import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { AlertCircle, Calendar, DollarSign, FileText, Users } from 'lucide-react';
import { Link } from 'wouter';

interface DashboardStats {
  todayAppointments: number;
  stockAlerts: number;
  unpaidInvoices: number;
  socialMessages: number;
}

function todayLocalDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    todayAppointments: 0,
    stockAlerts: 0,
    unpaidInvoices: 0,
    socialMessages: 0,
  });

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);
        const today = todayLocalDate();

        // Charger toutes les métriques en parallèle sans que l'une ne bloque les autres
        const [agendaRes, stockRes, facturesRes, socialRes] = await Promise.allSettled([
          api.get(`/agenda?date_debut=${today}T00:00:00&date_fin=${today}T23:59:59&vue=jour`),
          api.get('/injectables/stock'),
          api.get('/factures'),
          api.get('/social/analytics'),
        ]);

        // RDV aujourd'hui
        let todayAppointments = 0;
        if (agendaRes.status === 'fulfilled' && Array.isArray(agendaRes.value.data)) {
          todayAppointments = agendaRes.value.data.length;
        }

        // Alertes stock
        let stockAlerts = 0;
        if (stockRes.status === 'fulfilled' && stockRes.value.data?.total_alertes !== undefined) {
          stockAlerts = stockRes.value.data.total_alertes;
        }

        // Factures impayées ("brouillon" = pas encore envoyée, ce n'est
        // pas la même chose qu'"impayée" — les statuts qui comptent sont
        // envoyée et partiellement payée)
        let unpaidInvoices = 0;
        if (facturesRes.status === 'fulfilled' && Array.isArray(facturesRes.value.data)) {
          unpaidInvoices = facturesRes.value.data.filter((f: { statut: string }) =>
            ['envoyee', 'partiellement_payee'].includes(f.statut)
          ).length;
        }

        // Messages sociaux non traités
        let socialMessages = 0;
        if (socialRes.status === 'fulfilled' && socialRes.value.data?.messages) {
          const msgs = socialRes.value.data.messages;
          socialMessages = Object.values(msgs).reduce(
            (total: number, platformStats: any) => {
              return total + (platformStats.nouveau || 0);
            },
            0
          );
        }

        setStats({
          todayAppointments,
          stockAlerts,
          unpaidInvoices,
          socialMessages,
        });
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, []);

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
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">Tableau de bord</h1>
          <p className="text-muted-foreground mt-1">
            Bienvenue, {user?.prenom} {user?.nom}
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">RDV Aujourd'hui</CardTitle>
              <Calendar className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.todayAppointments}</div>
              <p className="text-xs text-muted-foreground">rendez-vous prévus</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alertes Stock</CardTitle>
              <AlertCircle className="h-4 w-4 text-destructive" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.stockAlerts}</div>
              <p className="text-xs text-muted-foreground">produits critiques</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Factures Impayées</CardTitle>
              <DollarSign className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.unpaidInvoices}</div>
              <p className="text-xs text-muted-foreground">en attente de paiement</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Messages Sociaux</CardTitle>
              <FileText className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.socialMessages}</div>
              <p className="text-xs text-muted-foreground">non traités</p>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Actions rapides</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Link
                href="/agenda"
                className="p-4 border rounded-lg hover:bg-muted transition-colors text-center"
              >
                <Calendar className="h-6 w-6 mx-auto mb-2 text-primary" />
                <p className="text-sm font-medium">Agenda</p>
              </Link>
              <Link
                href="/patients"
                className="p-4 border rounded-lg hover:bg-muted transition-colors text-center"
              >
                <Users className="h-6 w-6 mx-auto mb-2 text-primary" />
                <p className="text-sm font-medium">Patients</p>
              </Link>
              <Link
                href="/invoices"
                className="p-4 border rounded-lg hover:bg-muted transition-colors text-center"
              >
                <DollarSign className="h-6 w-6 mx-auto mb-2 text-primary" />
                <p className="text-sm font-medium">Factures</p>
              </Link>
              <Link
                href="/stock"
                className="p-4 border rounded-lg hover:bg-muted transition-colors text-center"
              >
                <AlertCircle className="h-6 w-6 mx-auto mb-2 text-primary" />
                <p className="text-sm font-medium">Stock</p>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
