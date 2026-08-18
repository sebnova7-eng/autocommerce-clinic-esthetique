import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  Plus,
  Edit2,
  Trash2,
  Play,
  BarChart3,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
} from 'lucide-react';

interface Workflow {
  id: number;
  nom: string;
  description?: string;
  trigger_type: string;
  enabled: boolean;
  status: string;
  created_at: string;
}

interface WorkflowStats {
  total_executions: number;
  completed: number;
  failed: number;
  drafts_awaiting_approval: number;
  success_rate: number;
}

export default function WorkflowEngine() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Charger les workflows
        const workflowsRes = await api.get('/workflows/');
        if (workflowsRes.data?.data) {
          setWorkflows(workflowsRes.data.data);
        }

        // Charger les statistiques
        const statsRes = await api.get('/workflows/statistics/summary');
        if (statsRes.data?.data) {
          setStats(statsRes.data.data);
        }
      } catch (err: any) {
        setError(err.message || 'Erreur lors du chargement des workflows');
        console.error('Workflow error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  const handleExecuteWorkflow = async (workflowId: number) => {
    try {
      await api.post(`/workflows/${workflowId}/execute`);
      // Recharger les données
      const workflowsRes = await api.get('/workflows/');
      if (workflowsRes.data?.data) {
        setWorkflows(workflowsRes.data.data);
      }
    } catch (err: any) {
      setError(err.message || 'Erreur lors de l\'exécution du workflow');
    }
  };

  const handleDeleteWorkflow = async (workflowId: number) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce workflow ?')) return;

    try {
      await api.delete(`/workflows/${workflowId}`);
      setWorkflows(workflows.filter(w => w.id !== workflowId));
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la suppression du workflow');
    }
  };

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
        {/* Titre et bouton */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Moteur de Workflows</h1>
            <p className="text-gray-600 mt-2">Automatisez vos processus cliniques</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            <Plus className="w-5 h-5" />
            Nouveau Workflow
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

        {/* Statistiques */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Total</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats.total_executions}</div>
                <p className="text-xs text-gray-500 mt-2">Exécutions (30j)</p>
              </CardContent>
            </Card>

            <Card className="border-green-200 bg-green-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-green-700">Réussies</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600">{stats.completed}</div>
                <p className="text-xs text-green-600 mt-2">✓ Complétées</p>
              </CardContent>
            </Card>

            <Card className="border-red-200 bg-red-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-red-700">Échouées</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-red-600">{stats.failed}</div>
                <p className="text-xs text-red-600 mt-2">✗ Erreurs</p>
              </CardContent>
            </Card>

            <Card className="border-yellow-200 bg-yellow-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-yellow-700">À valider</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-yellow-600">{stats.drafts_awaiting_approval}</div>
                <p className="text-xs text-yellow-600 mt-2">Brouillons à valider</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Taux réussite</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{(stats.success_rate || 0).toFixed(1)}%</div>
                <p className="text-xs text-gray-500 mt-2">Succès</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Liste des workflows */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {workflows.length === 0 ? (
            <Card className="lg:col-span-2">
              <CardContent className="pt-12 pb-12 text-center">
                <p className="text-gray-500">Aucun workflow créé. Commencez par en créer un !</p>
              </CardContent>
            </Card>
          ) : (
            workflows.map((workflow) => (
              <Card key={workflow.id} className={workflow.enabled ? '' : 'opacity-60'}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">{workflow.nom}</CardTitle>
                      {workflow.description && (
                        <p className="text-sm text-gray-600 mt-1">{workflow.description}</p>
                      )}
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      workflow.status === 'active' ? 'bg-green-100 text-green-700' :
                      workflow.status === 'paused' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {workflow.status}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-gray-600">Type de déclencheur</p>
                      <p className="text-sm font-medium capitalize">
                        {workflow.trigger_type.replace('_', ' ')}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Créé le</p>
                      <p className="text-sm font-medium">
                        {new Date(workflow.created_at).toLocaleDateString('fr-FR')}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 mt-4 pt-4 border-t">
                    <button
                      onClick={() => handleExecuteWorkflow(workflow.id)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition text-sm"
                    >
                      <Play className="w-4 h-4" />
                      Exécuter
                    </button>
                    <button
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-50 text-gray-600 rounded hover:bg-gray-100 transition text-sm"
                    >
                      <Edit2 className="w-4 h-4" />
                      Éditer
                    </button>
                    <button
                      onClick={() => handleDeleteWorkflow(workflow.id)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-red-50 text-red-600 rounded hover:bg-red-100 transition text-sm"
                    >
                      <Trash2 className="w-4 h-4" />
                      Supprimer
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Modèles prédéfinis */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Modèles prédéfinis
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { name: 'Rappel Anniversaire', icon: '🎂', color: 'bg-pink-100' },
                { name: 'Suivi Post-Opératoire', icon: '✓', color: 'bg-green-100' },
                { name: 'Relance Patient Inactif', icon: '📞', color: 'bg-orange-100' },
                { name: 'Relance Devis', icon: '📄', color: 'bg-blue-100' },
                { name: 'Suivi Injection', icon: '💉', color: 'bg-purple-100' },
                { name: 'Suivi Esthétique', icon: '✨', color: 'bg-yellow-100' },
              ].map((template, idx) => (
                <button
                  key={idx}
                  className={`p-4 rounded-lg text-center hover:shadow-lg transition ${template.color}`}
                >
                  <div className="text-3xl mb-2">{template.icon}</div>
                  <p className="font-medium text-sm">{template.name}</p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
