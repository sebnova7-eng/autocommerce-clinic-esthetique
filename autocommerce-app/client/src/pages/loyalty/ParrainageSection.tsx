import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { Copy, Users, Gift, CheckCircle } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export function ParrainageSection({ patientId }: { patientId: number }) {
  const [isLoading, setIsLoading] = useState(true);
  const [code, setCode] = useState('');
  const [filleuls, setFilleuls] = useState<any[]>([]);
  const [newFilleulId, setNewFilleulId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (patientId) {
      loadParrainageData();
    }
  }, [patientId]);

  const loadParrainageData = async () => {
    try {
      setIsLoading(true);
      const [codeRes, filleulsRes] = await Promise.all([
        api.get(`/parrainage/code/${patientId}`),
        api.get(`/parrainage/filleuls/${patientId}`)
      ]);
      setCode(codeRes.data.code);
      setFilleuls(filleulsRes.data);
    } catch (err) {
      toast.error('Erreur lors du chargement des données de parrainage');
    } finally {
      setIsLoading(false);
    }
  };

  const copyCode = () => {
    navigator.clipboard.writeText(code);
    toast.success('Code copié !');
  };

  const handleUseCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFilleulId) return;
    
    setIsSubmitting(true);
    try {
      await api.post('/parrainage/utiliser', {
        code: code,
        filleul_id: Number(newFilleulId)
      });
      toast.success('Parrainage validé !');
      setNewFilleulId('');
      loadParrainageData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la validation');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) return <div className="flex justify-center p-4"><Spinner /></div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gift className="w-5 h-5 text-primary" />
              Votre Code Parrain
            </CardTitle>
            <CardDescription>
              Partagez ce code avec vos amies. Vous recevrez 50 points chacune lors de leur premier soin.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input 
                  value={code} 
                  readOnly 
                  className="pr-10 font-mono text-lg text-center tracking-wider font-bold border-primary/30"
                />
              </div>
              <Button onClick={copyCode} variant="outline" size="icon">
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              Enregistrer un filleul
            </CardTitle>
            <CardDescription>
              Si une patiente vient de votre part, entrez son ID ici.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUseCode} className="flex gap-2">
              <Input 
                placeholder="ID de la patiente..." 
                value={newFilleulId}
                onChange={(e) => setNewFilleulId(e.target.value)}
              />
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Spinner className="h-4 w-4" /> : 'Valider'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mes Filleuls ({filleuls.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>ID Filleul</TableHead>
                <TableHead>Statut Récompense</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filleuls.map((f) => (
                <TableRow key={f.id}>
                  <TableCell>{new Date(f.date).toLocaleDateString()}</TableCell>
                  <TableCell>Patient #{f.filleul_id}</TableCell>
                  <TableCell>
                    {f.recompense_attribuee ? (
                      <span className="flex items-center gap-1 text-green-600 font-medium">
                        <CheckCircle className="w-4 h-4" /> +50 points attribués
                      </span>
                    ) : (
                      <span className="text-muted-foreground">En attente</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {filleuls.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                    Vous n'avez pas encore de filleuls.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
