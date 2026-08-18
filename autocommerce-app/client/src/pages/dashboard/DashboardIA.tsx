import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  AlertCircle,
  Calendar,
  DollarSign,
  FileText,
  TrendingUp,
  Users,
  AlertTriangle,
  Zap,
  BarChart3,
} from 'lucide-react';

interface DashboardIAData {
  timestamp: string;
  daily_summary: any;
  absent_patients: any;
  vip_patients: any;
  ai_recommendations: any;
  revenue_forecast: any;
  practitioner_performance: any;
  cancellation_risk: any;
  widgets_config: any;
}

export default function DashboardIA() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState<DashboardIAData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const response = await api.get('/dashboard-ia/full');
        if (response.data?.data) {
          setDashboardData(response.data.data);
        }
      } catch (err: any) {
        setError(err.message || 'Erreur lors du chargement du dashboard');
        console.error('Dashboard error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
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

  if (error) {
    return (
      <DashboardLayout>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      </DashboardLayout>
    );
  }

  if (!dashboardData) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-gray-500">Aucune donnée disponible</p>
        </div>
      </DashboardLayout>
    );
  }

  const { daily_summary, ai_recommendations, vip_patients, absent_patients, practitioner_performance, cancellation_risk } = dashboardData;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Titre */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard IA</h1>
          <p className="text-gray-600 mt-2">Vue d'ensemble intelligente de votre clinique</p>
        </div>

        {/* Résumé de la journée */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">RDV Aujourd'hui</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold">{daily_summary?.rdvs_today || 0}</div>
                <Calendar className="w-8 h-8 text-blue-500 opacity-50" />
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {daily_summary?.rdvs_tomorrow || 0} demain
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Revenus Aujourd'hui</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold">{daily_summary?.revenue_today?.toFixed(2) || 0} DT</div>
                <DollarSign className="w-8 h-8 text-green-500 opacity-50" />
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {daily_summary?.unpaid_invoices || 0} factures non payées
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Alertes Stock</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold text-orange-600">{daily_summary?.stock_alerts || 0}</div>
                <AlertTriangle className="w-8 h-8 text-orange-500 opacity-50" />
              </div>
              <p className="text-xs text-gray-500 mt-2">Produits à réapprovisionner</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Patients VIP</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold text-purple-600">{vip_patients?.total_vip || 0}</div>
                <Users className="w-8 h-8 text-purple-500 opacity-50" />
              </div>
              <p className="text-xs text-gray-500 mt-2">Clients fidèles</p>
            </CardContent>
          </Card>
        </div>

        {/* Rendez-vous d'aujourd'hui */}
        {daily_summary?.rdvs_today_details && daily_summary.rdvs_today_details.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Rendez-vous d'aujourd'hui
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {daily_summary.rdvs_today_details.map((rdv: any) => (
                  <div key={rdv.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium">{rdv.patient}</p>
                      <p className="text-sm text-gray-600">{rdv.acte}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{rdv.heure}</p>
                      <p className="text-sm text-gray-600">{rdv.salle}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recommandations IA */}
        {ai_recommendations?.recommendations && ai_recommendations.recommendations.length > 0 && (
          <Card className="border-blue-200 bg-blue-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-blue-900">
                <Zap className="w-5 h-5" />
                Recommandations IA
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {ai_recommendations.recommendations.map((rec: any, idx: number) => (
                  <div key={idx} className="p-3 bg-white rounded-lg border-l-4 border-blue-500">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{rec.message}</p>
                        {rec.products && (
                          <p className="text-sm text-gray-600 mt-1">
                            Produits: {rec.products.join(', ')}
                          </p>
                        )}
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        rec.priority === 'critical' ? 'bg-red-100 text-red-700' :
                        rec.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {rec.priority}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Patients absents */}
        {absent_patients?.patients && absent_patients.patients.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Patients absents ({absent_patients.total_absent_patients})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {absent_patients.patients.slice(0, 5).map((patient: any) => (
                  <div key={patient.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                    <div>
                      <p className="font-medium text-sm">{patient.nom}</p>
                      <p className="text-xs text-gray-600">{patient.telephone}</p>
                    </div>
                    <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded">
                      {patient.absences} absence(s)
                    </span>
                  </div>
                ))}
              </div>
              {absent_patients.total_absent_patients > 5 && (
                <p className="text-xs text-gray-500 mt-2">
                  +{absent_patients.total_absent_patients - 5} autres patients
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Risque prédictif d'annulation */}
        {cancellation_risk?.appointments && (
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-900">
                <AlertTriangle className="w-5 h-5" />
                Risque d'annulation des prochains RDV
              </CardTitle>
              <p className="text-sm text-amber-800">
                Base clinique : {(cancellation_risk.clinic_baseline_risk * 100).toFixed(1)} % — historique de {cancellation_risk.historical_appointments} RDV
              </p>
            </CardHeader>
            <CardContent>
              {cancellation_risk.appointments.length === 0 ? (
                <p className="text-sm text-gray-600">Aucun rendez-vous à risque dans les 30 prochains jours.</p>
              ) : (
                <div className="space-y-2">
                  {cancellation_risk.appointments.slice(0, 8).map((item: any) => (
                    <div key={item.rdv_id} className="flex items-center justify-between rounded-lg bg-white p-3">
                      <div>
                        <p className="font-medium">{item.patient || `Patient #${item.patient_id}`}</p>
                        <p className="text-xs text-gray-600">{new Date(item.date_heure).toLocaleString()} — {item.praticien || 'Praticien'}</p>
                      </div>
                      <span className={`rounded px-2 py-1 text-xs font-semibold ${item.risk_level === 'high' ? 'bg-red-100 text-red-700' : item.risk_level === 'medium' ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
                        {(item.risk_score * 100).toFixed(1)} %
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Performance des praticiens */}
        {practitioner_performance?.practitioners && practitioner_performance.practitioners.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Performance des praticiens
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {practitioner_performance.practitioners.map((practitioner: any) => (
                  <div key={practitioner.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-medium">{practitioner.nom}</p>
                      <p className="text-sm text-gray-600">{practitioner.specialite}</p>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <p className="text-gray-600">RDV</p>
                        <p className="font-bold">{practitioner.rdvs_completed}/{practitioner.rdvs_total}</p>
                      </div>
                      <div>
                        <p className="text-gray-600">Revenus</p>
                        <p className="font-bold">{practitioner.revenue.toFixed(2)} DT</p>
                      </div>
                      <div>
                        <p className="text-gray-600">Satisfaction</p>
                        <p className="font-bold">{practitioner.avg_satisfaction}/5</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Patients VIP */}
        {vip_patients?.patients && vip_patients.patients.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Patients VIP et GOLD
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {vip_patients.patients.slice(0, 5).map((patient: any) => (
                  <div key={patient.id} className="flex items-center justify-between p-2 bg-gradient-to-r from-purple-50 to-pink-50 rounded">
                    <div>
                      <p className="font-medium text-sm">{patient.nom}</p>
                      <p className="text-xs text-gray-600">{patient.points} points</p>
                    </div>
                    <div className="text-right">
                      <span className={`text-xs px-2 py-1 rounded font-medium ${
                        patient.niveau === 'vip' ? 'bg-purple-200 text-purple-700' : 'bg-yellow-200 text-yellow-700'
                      }`}>
                        {patient.niveau.toUpperCase()}
                      </span>
                      <p className="text-xs text-gray-600 mt-1">{patient.total_ca.toFixed(2)} DT</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
