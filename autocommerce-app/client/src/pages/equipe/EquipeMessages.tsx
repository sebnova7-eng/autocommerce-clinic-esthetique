import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Mail, MailOpen, Send, Trash2, Plus, Eye } from 'lucide-react';
import { authApi, equipeApi, EquipeMessage } from '@/lib/api';

// ── Types ────────────────────────────────────────────────────

interface UtilisateurOption {
  id: number;
  email: string;
  nom: string;
  prenom: string;
  role: string;
}

// ── Composant principal ──────────────────────────────────────

export default function EquipeMessages() {
  const [tab, setTab] = useState<'inbox' | 'sent'>('inbox');
  const [messages, setMessages] = useState<EquipeMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Composition
  const [composeOpen, setComposeOpen] = useState(false);
  const [destinataireId, setDestinataireId] = useState('');
  const [sujet, setSujet] = useState('');
  const [contenu, setContent] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [utilisateurs, setUtilisateurs] = useState<UtilisateurOption[]>([]);

  // Lecture
  const [readOpen, setReadOpen] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<EquipeMessage | null>(null);

  // Suppression
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // ── Chargement ────────────────────────────────────────────

  const loadMessages = async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (tab === 'inbox') {
        const res = await equipeApi.getInbox();
        setMessages(res.data);
      } else {
        const res = await equipeApi.getSent();
        setMessages(res.data);
      }
    } catch {
      setError('Impossible de charger les messages.');
      toast.error('Erreur lors du chargement des messages');
    } finally {
      setIsLoading(false);
    }
  };

  const loadUnread = async () => {
    try {
      const res = await equipeApi.getUnreadCount();
      setUnreadCount(res.data.unread_count);
    } catch {
      // Silencieux — pas bloquant
    }
  };

  const loadUtilisateurs = async () => {
    try {
      // Le profil est chargé via le client privé centralisé ; aucun token n’est
      // lu directement depuis le stockage navigateur.
      await authApi.me();
      // On utilise l'endpoint des candidatures ou un endpoint existant pour lister les utilisateurs
      // Pour simplifier, on utilise l'endpoint /auth/me et on liste les messages existants
      // pour extraire les destinataires, puis on laisse l'utilisateur saisir l'ID.
      // En production, un endpoint /users listerait les membres de l'équipe.
      setUtilisateurs([]);
    } catch {
      setUtilisateurs([]);
    }
  };

  useEffect(() => {
    loadMessages();
    loadUnread();
  }, [tab]);

  useEffect(() => {
    loadUtilisateurs();
  }, []);

  // ── Handlers ──────────────────────────────────────────────

  const handleSend = async () => {
    if (!destinataireId || !sujet.trim() || !contenu.trim()) {
      toast.error('Tous les champs sont obligatoires');
      return;
    }
    setIsSending(true);
    try {
      await equipeApi.send({
        destinataire_id: parseInt(destinataireId),
        sujet: sujet.trim(),
        contenu: contenu.trim(),
      });
      toast.success('Message envoyé avec succès');
      setComposeOpen(false);
      setDestinataireId('');
      setSujet('');
      setContent('');
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erreur lors de l\'envoi');
    } finally {
      setIsSending(false);
    }
  };

  const handleRead = async (msg: EquipeMessage) => {
    setSelectedMessage(msg);
    setReadOpen(true);
    // Marquer comme lu si c'est un message reçu non lu
    if (!msg.lu && tab === 'inbox') {
      try {
        await equipeApi.markRead(msg.id);
        msg.lu = true;
        msg.lu_a = new Date().toISOString();
        loadUnread();
      } catch {
        // Silencieux
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await equipeApi.delete(deleteId);
      toast.success('Message supprimé');
      setDeleteOpen(false);
      setDeleteId(null);
      setReadOpen(false);
      setSelectedMessage(null);
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erreur lors de la suppression');
    }
  };

  const handleOpenDelete = (id: number) => {
    setDeleteId(id);
    setDeleteOpen(true);
  };

  // ── Rendu ─────────────────────────────────────────────────

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Messagerie Équipe</h1>
            <p className="text-muted-foreground">
              Communication interne entre les membres de la clinique
            </p>
          </div>
          <Button onClick={() => setComposeOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Nouveau message
          </Button>
        </div>

        {/* Tabs */}
        <Tabs value={tab} onValueChange={(v) => setTab(v as 'inbox' | 'sent')}>
          <TabsList>
            <TabsTrigger value="inbox" className="relative">
              {unreadCount > 0 ? (
                <>
                  <Mail className="w-4 h-4 mr-2" />
                  Boîte de réception
                  <Badge variant="destructive" className="ml-2 h-5 min-w-[20px] px-1">
                    {unreadCount}
                  </Badge>
                </>
              ) : (
                <>
                  <MailOpen className="w-4 h-4 mr-2" />
                  Boîte de réception
                </>
              )}
            </TabsTrigger>
            <TabsTrigger value="sent">
              <Send className="w-4 h-4 mr-2" />
              Envoyés
            </TabsTrigger>
          </TabsList>

          <TabsContent value={tab} className="mt-4">
            <Card>
              <CardContent className="p-0">
                {isLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Spinner className="size-8" />
                  </div>
                ) : error ? (
                  <div className="flex items-center justify-center py-12 text-muted-foreground">
                    {error}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Mail className="w-12 h-12 mb-4 opacity-30" />
                    <p>Aucun message {tab === 'inbox' ? 'reçu' : 'envoyé'}</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {tab === 'inbox' ? (
                          <>
                            <TableHead>De</TableHead>
                            <TableHead>Sujet</TableHead>
                            <TableHead>Date</TableHead>
                            <TableHead className="w-[100px]">Actions</TableHead>
                          </>
                        ) : (
                          <>
                            <TableHead>À</TableHead>
                            <TableHead>Sujet</TableHead>
                            <TableHead>Date</TableHead>
                            <TableHead>Statut</TableHead>
                            <TableHead className="w-[100px]">Actions</TableHead>
                          </>
                        )}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {messages.map((msg) => (
                        <TableRow
                          key={msg.id}
                          className={!msg.lu && tab === 'inbox' ? 'bg-blue-50 font-medium' : ''}
                        >
                          {tab === 'inbox' ? (
                            <>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  {!msg.lu && (
                                    <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                                  )}
                                  <span>
                                    {msg.expediteur_prenom} {msg.expediteur_nom}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell className="max-w-[300px] truncate">
                                {msg.sujet}
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {formatDate(msg.cree_a)}
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRead(msg)}
                                    title="Lire"
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title="Supprimer"
                                  >
                                    <Trash2 className="w-4 h-4 text-red-500" />
                                  </Button>
                                </div>
                              </TableCell>
                            </>
                          ) : (
                            <>
                              <TableCell>
                                {msg.destinataire_prenom} {msg.destinataire_nom}
                              </TableCell>
                              <TableCell className="max-w-[300px] truncate">
                                {msg.sujet}
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {formatDate(msg.cree_a)}
                              </TableCell>
                              <TableCell>
                                <Badge variant={msg.lu ? 'default' : 'secondary'}>
                                  {msg.lu ? 'Lu' : 'Non lu'}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRead(msg)}
                                    title="Voir"
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title="Supprimer"
                                  >
                                    <Trash2 className="w-4 h-4 text-red-500" />
                                  </Button>
                                </div>
                              </TableCell>
                            </>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Dialog : Composer ─────────────────────────────── */}
      <Dialog open={composeOpen} onOpenChange={setComposeOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nouveau message</DialogTitle>
            <DialogDescription>
              Envoyez un message à un membre de l'équipe.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="destinataire">Destinataire (ID utilisateur)</Label>
              <Input
                id="destinataire"
                placeholder="ID de l'utilisateur destinataire"
                value={destinataireId}
                onChange={(e) => setDestinataireId(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                L'ID de l'utilisateur destinataire (visible dans les paramètres)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="sujet">Sujet</Label>
              <Input
                id="sujet"
                placeholder="Objet du message"
                value={sujet}
                onChange={(e) => setSujet(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contenu">Message</Label>
              <Textarea
                id="contenu"
                placeholder="Rédigez votre message..."
                rows={6}
                value={contenu}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setComposeOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSend} disabled={isSending}>
              {isSending ? <Spinner className="w-4 h-4 mr-2" /> : <Send className="w-4 h-4 mr-2" />}
              Envoyer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog : Lire un message ──────────────────────── */}
      <Dialog open={readOpen} onOpenChange={setReadOpen}>
        <DialogContent className="max-w-lg">
          {selectedMessage && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedMessage.sujet}</DialogTitle>
                <DialogDescription>
                  {tab === 'inbox' ? (
                    <>
                      De : <strong>{selectedMessage.expediteur_prenom} {selectedMessage.expediteur_nom}</strong>
                    </>
                  ) : (
                    <>
                      À : <strong>{selectedMessage.destinataire_prenom} {selectedMessage.destinataire_nom}</strong>
                    </>
                  )}
                  {' '}&mdash; {formatDate(selectedMessage.cree_a)}
                  {selectedMessage.lu && selectedMessage.lu_a && (
                    <>
                      <br />
                      <span className="text-xs text-muted-foreground">
                        Lu le {formatDate(selectedMessage.lu_a)}
                      </span>
                    </>
                  )}
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <p className="whitespace-pre-wrap text-sm">{selectedMessage.contenu}</p>
              </div>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setReadOpen(false);
                    handleOpenDelete(selectedMessage.id);
                  }}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Supprimer
                </Button>
                <Button onClick={() => setReadOpen(false)}>Fermer</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Alert : Confirmer suppression ─────────────────── */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce message ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Le message sera définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DashboardLayout>
  );
}
