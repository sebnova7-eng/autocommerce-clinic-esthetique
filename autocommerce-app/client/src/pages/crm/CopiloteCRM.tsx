import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  Search,
  FileText,
  AlertCircle,
  MessageSquare,
  Mail,
  TrendingDown,
  CheckCircle,
  Clock,
  Zap,
} from 'lucide-react';

interface PatientSummary {
  patient_id: number;
  data: {
    patient: {
      id: number;
      prenom: string;
      nom: string;
      email: string | null;
      telephone: string | null;
      notes: string | null;
    };
    actes_summary: Record<string, {
      count: number;
      last_date: string | null;
      avg_satisfaction: number | null;
    }>;
    rdvs: {
      total: number;
      completed: number;
      cancelled: number;
      no_show: number;
      next: { id: number; date: string; acte: string | null; praticien: string | null } | null;
    };
    factures: { count: number };
    photos: { series_count: number };
  };
  llm_summary: string | null;
  llm_status: string;
}

interface AtRiskPatient {
  patient_id: number;
  patient_name: string;
  risk_score: number;
  risk_level: 'critical' | 'high' | 'medium';
  reasons: string[];
}

export default function CopiloteCRM() {
  const { user } = useAuth();
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [patientSummary, setPatientSummary] = useState<PatientSummary | null>(null);
  const [atRiskPatients, setAtRiskPatients] = useState<AtRiskPatient[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'summary' | 'at-risk' | 'draft'>('summary');

  const loadPatientSummary = async (patientId: number) => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.get(`/copilote-crm/patient/${patientId}/summary`);
      if (response.data?.data) {
        setPatientSummary(response.data.data);
        setSelectedPatientId(patientId);
      }
    } catch (err: any) {
      setError(err.message || 'Erreur lors du chargement du résumé');
    } finally {
      setIsLoading(false);
    }
  };

  const loadAtRiskPatients = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.get('/copilote-crm/at-risk-patients');
      const payload = response.data?.data;
      if (payload) {
        const now = Date.now();
        const items = Array.isArray(payload.items) ? payload.items : [];
        setAtRiskPatients(items.map((item: { id: number; name?: string; last_visit?: string | null }) => {
          const lastVisit = item.last_visit ? new Date(item.last_visit).getTime() : null;
          const daysSinceVisit = lastVisit ? Math.max(0, Math.floor((now - lastVisit) / 86400000)) : null;
          const riskScore = daysSinceVisit === null
            ? 100
            : Math.min(100, Math.round((daysSinceVisit / 120) * 100));
          const riskLevel = riskScore >= 80 ? 'critical' : riskScore >= 50 ? 'high' : 'medium';
          return {
            patient_id: item.id,
            patient_name: item.name?.trim() || `Patient #${item.id}`,
            risk_score: riskScore,
            risk_level: riskLevel,
            reasons: [
              daysSinceVisit === null
                ? 'Aucune visite enregistrée'
                : `Dernière visite il y a ${daysSinceVisit} jour${daysSinceVisit > 1 ? 's' : ''}`,
            ],
          };
        }));
      }
    } catch (err: any) {
      setError(err.message || 'Erreur lors du chargement des patients à risque');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadAtRiskPatients();
  }, []);

  const totalActes = patientSummary
    ? Object.values(patientSummary.data.actes_summary).reduce((total, acte) => total + acte.count, 0)
    : 0;

  if (isLoading && !patientSummary) {
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
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Copilote CRM</h1>
          <p className="text-gray-600 mt-2">Assistant intelligent pour la gestion des patients</p>
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

        {/* Onglets */}
        <div className="flex gap-2 border-b">
          <button
            onClick={() => setActiveTab('summary')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'summary'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Résumé Patient
          </button>
          <button
            onClick={() => setActiveTab('at-risk')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'at-risk'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <AlertCircle className="w-4 h-4 inline mr-2" />
            Patients à Risque ({atRiskPatients.length})
          </button>
          <button
            onClick={() => setActiveTab('draft')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'draft'
                ? 'border-green-600 text-green-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <MessageSquare className="w-4 h-4 inline mr-2" />
            Brouillons
          </button>
        </div>

        {/* Onglet Résumé Patient */}
        {activeTab === 'summary' && (
          <div className="space-y-6">
            {/* Recherche patient */}
            <Card>
              <CardHeader>
                <CardTitle>Rechercher un patient</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <input
                    type="number"
                    placeholder="ID du patient"
                    className="flex-1 px-3 py-2 border rounded-lg"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        const patientId = parseInt((e.target as HTMLInputElement).value);
                        if (patientId) loadPatientSummary(patientId);
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const input = document.querySelector('input[type="number"]') as HTMLInputElement;
                      if (input?.value) loadPatientSummary(parseInt(input.value));
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                </div>
              </CardContent>
            </Card>

            {/* Résumé du patient */}
            {patientSummary && (
              <div className="space-y-4">
                {/* Infos patient */}
                <Card>
                  <CardHeader>
                    <CardTitle>{`${patientSummary.data.patient.prenom} ${patientSummary.data.patient.nom}`.trim()}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">Téléphone</p>
                        <p className="font-medium">{patientSummary.data.patient.telephone || 'Non renseigné'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Email</p>
                        <p className="font-medium">{patientSummary.data.patient.email || 'Non renseigné'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Notes</p>
                        <p className="font-medium">{patientSummary.data.patient.notes || 'Aucune note'}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Historique médical */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="w-5 h-5" />
                      Historique Médical
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm text-gray-600">Total d'actes</p>
                        <p className="text-2xl font-bold">{totalActes}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-2">Actes effectués</p>
                        <div className="space-y-1">
                          {Object.entries(patientSummary.data.actes_summary).map(([acte, data]: any) => (
                            <div key={acte} className="text-sm">
                              <span className="font-medium">{acte}</span>
                              <span className="text-gray-600"> - {data.count} fois</span>
                              {data.avg_satisfaction && (
                                <span className="text-yellow-600"> - ⭐ {data.avg_satisfaction.toFixed(1)}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Rendez-vous */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Clock className="w-5 h-5" />
                      Rendez-vous
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">Total</p>
                        <p className="text-2xl font-bold">{patientSummary.data.rdvs.total}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Complétés</p>
                        <p className="text-2xl font-bold text-green-600">{patientSummary.data.rdvs.completed}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Annulés</p>
                        <p className="text-2xl font-bold text-orange-600">{patientSummary.data.rdvs.cancelled}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">No-show</p>
                        <p className="text-2xl font-bold text-red-600">{patientSummary.data.rdvs.no_show}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Finances */}
                <Card>
                  <CardHeader>
                    <CardTitle>Finances</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">Factures</p>
                        <p className="text-2xl font-bold">{patientSummary.data.factures.count}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Séries photos</p>
                        <p className="text-2xl font-bold text-blue-600">{patientSummary.data.photos.series_count}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        {/* Onglet Patients à Risque */}
        {activeTab === 'at-risk' && (
          <div className="space-y-4">
            {atRiskPatients.length === 0 ? (
              <Card>
                <CardContent className="pt-12 pb-12 text-center">
                  <p className="text-gray-500">Aucun patient à risque détecté</p>
                </CardContent>
              </Card>
            ) : (
              atRiskPatients.map((patient) => (
                <Card
                  key={patient.patient_id}
                  className={
                    patient.risk_level === 'critical'
                      ? 'border-red-300 bg-red-50'
                      : patient.risk_level === 'high'
                      ? 'border-orange-300 bg-orange-50'
                      : 'border-yellow-300 bg-yellow-50'
                  }
                >
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-bold text-lg">{patient.patient_name}</p>
                        <p className="text-sm text-gray-600 mt-1">Score de risque: {patient.risk_score}/100</p>
                        <div className="mt-2 space-y-1">
                          {patient.reasons.map((reason, idx) => (
                            <p key={idx} className="text-sm text-gray-700">• {reason}</p>
                          ))}
                        </div>
                      </div>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-bold ${
                          patient.risk_level === 'critical'
                            ? 'bg-red-200 text-red-800'
                            : patient.risk_level === 'high'
                            ? 'bg-orange-200 text-orange-800'
                            : 'bg-yellow-200 text-yellow-800'
                        }`}
                      >
                        {patient.risk_level.toUpperCase()}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedPatientId(patient.patient_id);
                        loadPatientSummary(patient.patient_id);
                        setActiveTab('summary');
                      }}
                      className="mt-4 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                    >
                      Voir le dossier
                    </button>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {/* Onglet Brouillons */}
        {activeTab === 'draft' && (
          <Card>
            <CardHeader>
              <CardTitle>Brouillons de messages</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">
                Les brouillons de messages WhatsApp et email apparaîtront ici une fois qu'un patient sera sélectionné.
              </p>
              {selectedPatientId && (
                <div className="mt-4 space-y-4">
                  <button className="w-full px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" />
                    Générer brouillon WhatsApp
                  </button>
                  <button className="w-full px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    Générer brouillon Email
                  </button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
