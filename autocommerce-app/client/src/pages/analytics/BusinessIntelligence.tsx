import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  TrendingUp,
  Users,
  Zap,
  AlertCircle,
  Download,
  BarChart3,
  DollarSign,
  Calendar,
} from 'lucide-react';

interface RevenueSummary {
  total_revenue: number;
  total_invoices: number;
  avg_invoice: number;
  revenue_by_practitioner: Record<string, any>;
  revenue_by_acte: Record<string, any>;
}

interface TopPractitioner {
  name: string;
  revenue: number;
  unique_patients: number;
  completed_rdvs: number;
  avg_satisfaction: number;
}

interface TopTreatment {
  name: string;
  revenue: number;
  count: number;
  unique_patients: number;
  avg_satisfaction: number;
}

export default function BusinessIntelligence() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'practitioners' | 'treatments' | 'patients' | 'forecast'>('overview');

  const [revenueSummary, setRevenueSummary] = useState<RevenueSummary | null>(null);
  const [topPractitioners, setTopPractitioners] = useState<TopPractitioner[]>([]);
  const [topTreatments, setTopTreatments] = useState<TopTreatment[]>([]);
  const [topPatients, setTopPatients] = useState<any[]>([]);
  const [forecast, setForecast] = useState<any>(null);
  const [kpis, setKpis] = useState<any>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [revRes, practRes, treatRes, patRes, foreRes, kpiRes] = await Promise.all([
          api.get('/business-intelligence/revenue-summary'),
          api.get('/business-intelligence/top-practitioners'),
          api.get('/business-intelligence/top-treatments'),
          api.get('/business-intelligence/top-loyal-patients'),
          api.get('/business-intelligence/revenue-forecast'),
          api.get('/business-intelligence/kpi-dashboard'),
        ]);

        if (revRes.data?.data) setRevenueSummary(revRes.data.data);
        if (practRes.data?.data) setTopPractitioners(practRes.data.data.top_practitioners || []);
        if (treatRes.data?.data) setTopTreatments(treatRes.data.data.top_treatments || []);
        if (patRes.data?.data) setTopPatients(patRes.data.data.top_patients || []);
        if (foreRes.data?.data) setForecast(foreRes.data.data);
        if (kpiRes.data?.data) setKpis(kpiRes.data.data.kpis);
      } catch (err: any) {
        setError(err.message || 'Erreur lors du chargement des données');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Titre */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Business Intelligence</h1>
            <p className="text-gray-600 mt-2">Analyses et rapports détaillés</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Download className="w-5 h-5" />
            Exporter Rapport
          </button>
        </div>

        {/* Erreur */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* KPIs */}
        {kpis && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Revenus Aujourd'hui</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{kpis.revenue_today.toFixed(2)} DT</div>
                <p className="text-xs text-gray-500 mt-2">Factures payées</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Revenus du Mois</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{kpis.revenue_month.toFixed(2)} DT</div>
                <p className="text-xs text-gray-500 mt-2">Cumul mensuel</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">RDV Aujourd'hui</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{kpis.rdvs_today}</div>
                <p className="text-xs text-gray-500 mt-2">Rendez-vous planifiés</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Patients Actifs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{kpis.total_active_patients}</div>
                <p className="text-xs text-gray-500 mt-2">Base active</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Onglets */}
        <div className="flex gap-2 border-b overflow-x-auto">
          {[
            { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
            { id: 'practitioners', label: 'Praticiens', icon: Users },
            { id: 'treatments', label: 'Soins', icon: Zap },
            { id: 'patients', label: 'Patients', icon: Users },
            { id: 'forecast', label: 'Prévisions', icon: TrendingUp },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-4 py-2 font-medium border-b-2 transition whitespace-nowrap flex items-center gap-2 ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Vue d'ensemble */}
        {activeTab === 'overview' && revenueSummary && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Résumé des Revenus (30 derniers jours)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <p className="text-sm text-gray-600">Revenu Total</p>
                    <p className="text-3xl font-bold text-green-600">{revenueSummary.total_revenue.toFixed(2)} DT</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Nombre de Factures</p>
                    <p className="text-3xl font-bold">{revenueSummary.total_invoices}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Facture Moyenne</p>
                    <p className="text-3xl font-bold">{revenueSummary.avg_invoice.toFixed(2)} DT</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top 5 Actes par Revenu</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(revenueSummary.revenue_by_acte)
                    .sort(([, a]: any, [, b]: any) => b.revenue - a.revenue)
                    .slice(0, 5)
                    .map(([acte, data]: any) => (
                      <div key={acte} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                        <div>
                          <p className="font-medium">{acte}</p>
                          <p className="text-sm text-gray-600">{data.count} fois</p>
                        </div>
                        <p className="font-bold">{data.revenue.toFixed(2)} DT</p>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Praticiens */}
        {activeTab === 'practitioners' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {topPractitioners.map((practitioner, idx) => (
              <Card key={idx}>
                <CardHeader>
                  <CardTitle>{practitioner.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Revenu</span>
                      <span className="font-bold">{practitioner.revenue.toFixed(2)} DT</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Patients uniques</span>
                      <span className="font-bold">{practitioner.unique_patients}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">RDV complétés</span>
                      <span className="font-bold">{practitioner.completed_rdvs}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Satisfaction</span>
                      <span className="font-bold">⭐ {practitioner.avg_satisfaction}/5</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Soins */}
        {activeTab === 'treatments' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {topTreatments.map((treatment, idx) => (
              <Card key={idx}>
                <CardHeader>
                  <CardTitle>{treatment.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Revenu Total</span>
                      <span className="font-bold">{treatment.revenue.toFixed(2)} DT</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Nombre de fois</span>
                      <span className="font-bold">{treatment.count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Patients uniques</span>
                      <span className="font-bold">{treatment.unique_patients}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Satisfaction</span>
                      <span className="font-bold">⭐ {treatment.avg_satisfaction}/5</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Patients */}
        {activeTab === 'patients' && (
          <Card>
            <CardHeader>
              <CardTitle>Top Patients Fidèles</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {topPatients.map((patient) => (
                  <div key={patient.id} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <p className="font-medium">{patient.name}</p>
                      <p className="text-sm text-gray-600">{patient.visits} visites</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold">{patient.total_ca.toFixed(2)} DT</p>
                      <span className={`text-xs px-2 py-1 rounded ${
                        patient.loyalty_level === 'vip' ? 'bg-purple-100 text-purple-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {patient.loyalty_level.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Prévisions */}
        {activeTab === 'forecast' && forecast && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Prévision des Revenus (30 jours)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Total prévu</p>
                    <p className="text-3xl font-bold text-blue-600">{forecast.total_forecast.toFixed(2)} DT</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Moyenne quotidienne</p>
                    <p className="text-3xl font-bold">{forecast.avg_daily_revenue.toFixed(2)} DT</p>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-2">Répartition par jour</p>
                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {(Object.entries(forecast.forecast_by_day) as [string, number][])
                      .slice(-7)
                      .map(([day, revenue]) => (
                        <div key={day} className="flex items-center justify-between text-sm">
                          <span>{new Date(day).toLocaleDateString('fr-FR')}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-32 bg-gray-200 rounded h-2">
                              <div
                                className="bg-blue-600 h-2 rounded"
                                style={{
                                  width: `${(revenue / Math.max(...(Object.values(forecast.forecast_by_day) as number[]))) * 100}%`,
                                }}
                              />
                            </div>
                            <span className="font-medium">{revenue.toFixed(2)} DT</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
