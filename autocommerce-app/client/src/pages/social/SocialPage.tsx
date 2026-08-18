import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface SocialMessage {
  id: number;
  plateforme: string;
  contact_nom: string | null;
  contact_id: string;
  contenu: string;
  statut: string; // nouveau | traite | repondu
  created_at: string;
}

interface SocialPost {
  id: number;
  plateforme: string;
  contenu: string;
  statut: string; // brouillon | planifie | publie | echec
  date_publication_prevue: string | null;
  erreur: string | null;
}

interface SocialAvis {
  id: number;
  plateforme: string;
  note: number | null;
  texte: string;
  auteur_nom: string | null;
  reponse_suggeree_ia: string | null;
  reponse_publiee: string | null;
  statut: string; // nouveau | suggere | valide | publie
  created_at: string;
}

const MESSAGE_STATUT: Record<string, { label: string; color: string }> = {
  nouveau: { label: 'Nouveau', color: 'bg-yellow-100 text-yellow-800' },
  traite: { label: 'Traité', color: 'bg-blue-100 text-blue-800' },
  repondu: { label: 'Répondu', color: 'bg-green-100 text-green-800' },
};

const POST_STATUT: Record<string, { label: string; color: string }> = {
  brouillon: { label: 'Brouillon', color: 'bg-gray-100 text-gray-800' },
  planifie: { label: 'Planifié', color: 'bg-blue-100 text-blue-800' },
  publie: { label: 'Publié', color: 'bg-green-100 text-green-800' },
  echec: { label: 'Échec', color: 'bg-red-100 text-red-800' },
};

const AVIS_STATUT: Record<string, { label: string; color: string }> = {
  nouveau: { label: 'Nouveau', color: 'bg-yellow-100 text-yellow-800' },
  suggere: { label: 'IA Suggérée', color: 'bg-purple-100 text-purple-800' },
  valide: { label: 'Validé', color: 'bg-blue-100 text-blue-800' },
  publie: { label: 'Publié', color: 'bg-green-100 text-green-800' },
};

// WhatsApp est le seul canal réellement branché (webhook + token Meta) à
// ce stade — Instagram/Facebook/TikTok sont annoncés comme non connectés
// tant qu'aucune vraie clé API n'est fournie côté backend, conformément
// au cahier des charges ("affiche cet état clairement, ne le traite pas
// comme une erreur générique").
const PLATFORM_STATUS: Record<string, 'connecte' | 'non_connecte'> = {
  whatsapp: 'connecte',
  instagram: 'non_connecte',
  facebook: 'non_connecte',
  tiktok: 'non_connecte',
};

export default function SocialPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [messages, setMessages] = useState<SocialMessage[]>([]);
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [avis, setAvis] = useState<SocialAvis[]>([]);
  const [activeTab, setActiveTab] = useState('messages');
  const [replyTarget, setReplyTarget] = useState<SocialMessage | null>(null);
  const [avisTarget, setAvisTarget] = useState<SocialAvis | null>(null);
  const [newPostOpen, setNewPostOpen] = useState(false);

  useEffect(() => {
    loadSocialData();
  }, []);

  const loadSocialData = async () => {
    try {
      setIsLoading(true);
      const [messagesRes, postsRes, avisRes] = await Promise.all([
        api.get('/social/messages'),
        api.get('/social/posts'),
        api.get('/social/avis'),
      ]);
      // Les endpoints renvoient un tableau brut
      setMessages(Array.isArray(messagesRes.data) ? messagesRes.data : []);
      setPosts(Array.isArray(postsRes.data) ? postsRes.data : []);
      setAvis(Array.isArray(avisRes.data) ? avisRes.data : []);
    } catch (err: any) {
      console.error('Failed to load social data:', err);
      toast.error('Erreur lors du chargement des données sociales');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePublierPost = async (post: SocialPost) => {
    try {
      await api.post(`/social/posts/${post.id}/publier`);
      toast.success('Post publié');
      loadSocialData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la publication');
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Social CRM</h1>
            <p className="text-muted-foreground mt-1">Gestion des réseaux sociaux</p>
          </div>
          <Button onClick={() => setNewPostOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Nouveau post
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">État des connexions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              {Object.entries(PLATFORM_STATUS).map(([platform, status]) => (
                <div key={platform} className="p-3 border rounded-lg">
                  <p className="text-sm font-medium capitalize">{platform}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <div className={`w-2 h-2 rounded-full ${status === 'connecte' ? 'bg-green-500' : 'bg-gray-400'}`} />
                    <span className="text-xs text-muted-foreground">
                      {status === 'connecte' ? 'Connecté' : 'Non connecté'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="messages">Messages ({messages.length})</TabsTrigger>
            <TabsTrigger value="posts">Posts ({posts.length})</TabsTrigger>
            <TabsTrigger value="avis">Avis ({avis.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="messages" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {messages.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucun message</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Plateforme</TableHead>
                          <TableHead>Contact</TableHead>
                          <TableHead>Contenu</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Date</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {messages.map((msg) => {
                          const s = MESSAGE_STATUT[msg.statut] || { label: msg.statut, color: 'bg-gray-100 text-gray-800' };
                          return (
                            <TableRow key={msg.id}>
                              <TableCell className="font-medium capitalize">{msg.plateforme}</TableCell>
                              <TableCell className="text-sm">{msg.contact_nom || msg.contact_id}</TableCell>
                              <TableCell className="text-sm max-w-xs truncate">{msg.contenu}</TableCell>
                              <TableCell>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {new Date(msg.created_at).toLocaleDateString('fr-FR')}
                              </TableCell>
                              <TableCell>
                                {msg.statut !== 'repondu' && (
                                  <Button variant="outline" size="sm" onClick={() => setReplyTarget(msg)}>
                                    Répondre
                                  </Button>
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="posts" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {posts.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucun post</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Plateforme</TableHead>
                          <TableHead>Contenu</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Date prévue</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {posts.map((post) => {
                          const s = POST_STATUT[post.statut] || { label: post.statut, color: 'bg-gray-100 text-gray-800' };
                          return (
                            <TableRow key={post.id}>
                              <TableCell className="font-medium capitalize">{post.plateforme}</TableCell>
                              <TableCell className="text-sm max-w-xs truncate">{post.contenu}</TableCell>
                              <TableCell>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                                {post.erreur && <p className="text-xs text-destructive mt-1">{post.erreur}</p>}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {post.date_publication_prevue ? new Date(post.date_publication_prevue).toLocaleDateString('fr-FR') : '—'}
                              </TableCell>
                              <TableCell>
                                {(post.statut === 'brouillon' || post.statut === 'planifie') && (
                                  <Button variant="outline" size="sm" onClick={() => handlePublierPost(post)}>
                                    Publier
                                  </Button>
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="avis" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {avis.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">Aucun avis client</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Plateforme</TableHead>
                          <TableHead>Auteur / Note</TableHead>
                          <TableHead>Texte</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {avis.map((a) => {
                          const s = AVIS_STATUT[a.statut] || { label: a.statut, color: 'bg-gray-100 text-gray-800' };
                          return (
                            <TableRow key={a.id}>
                              <TableCell className="font-medium capitalize">{a.plateforme}</TableCell>
                              <TableCell className="text-sm">
                                <div className="font-semibold">{a.auteur_nom || 'Anonyme'}</div>
                                <div className="text-yellow-600">{a.note ? '★'.repeat(a.note) : '—'}</div>
                              </TableCell>
                              <TableCell className="text-sm max-w-md">
                                <p className="line-clamp-2">{a.texte}</p>
                              </TableCell>
                              <TableCell>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${s.color}`}>{s.label}</span>
                              </TableCell>
                              <TableCell>
                                <Button variant="outline" size="sm" onClick={() => setAvisTarget(a)}>
                                  {a.statut === 'publie' ? 'Voir' : 'Répondre'}
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <ReplyDialog message={replyTarget} onOpenChange={() => setReplyTarget(null)} onReplied={loadSocialData} />
      <AvisReplyDialog avis={avisTarget} onOpenChange={() => setAvisTarget(null)} onUpdated={loadSocialData} />
      <NewPostDialog open={newPostOpen} onOpenChange={setNewPostOpen} onCreated={loadSocialData} />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────

function AvisReplyDialog({ avis, onOpenChange, onUpdated }: {
  avis: SocialAvis | null; onOpenChange: () => void; onUpdated: () => void;
}) {
  const [reponse, setReponse] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (avis) {
      setReponse(avis.reponse_publiee || avis.reponse_suggeree_ia || '');
    }
  }, [avis]);

  const handleSuggestIA = async () => {
    if (!avis) return;
    setIsGenerating(true);
    try {
      const res = await api.post(`/social/avis/${avis.id}/suggerer-reponse`);
      setReponse(res.data.reponse_suggeree);
      toast.success('Suggestion IA générée');
    } catch (err: any) {
      toast.error('Erreur lors de la génération IA');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleValidate = async () => {
    if (!avis || !reponse.trim()) return;
    setIsSaving(true);
    try {
      await api.post(`/social/avis/${avis.id}/valider`, { reponse_finale: reponse.trim() });
      toast.success('Réponse validée et publiée');
      onOpenChange();
      onUpdated();
    } catch (err: any) {
      toast.error("Erreur lors de la validation");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!avis} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Gérer l'avis client</DialogTitle>
          <DialogDescription>
            {avis?.auteur_nom} sur {avis?.plateforme} ({avis?.note}/5)
          </DialogDescription>
        </DialogHeader>
        {avis && (
          <div className="bg-muted rounded-md p-3 text-sm italic">"{avis.texte}"</div>
        )}
        <div className="space-y-2 mt-4">
          <div className="flex justify-between items-center">
            <Label htmlFor="avis-reply">Réponse à publier</Label>
            {avis?.statut !== 'publie' && (
              <Button variant="ghost" size="sm" onClick={handleSuggestIA} disabled={isGenerating}>
                {isGenerating ? <Spinner className="h-3 w-3 mr-2" /> : null}
                Générer avec IA
              </Button>
            )}
          </div>
          <Textarea
            id="avis-reply"
            value={reponse}
            onChange={(e) => setReponse(e.target.value)}
            rows={6}
            placeholder="Écrivez votre réponse ici..."
            disabled={avis?.statut === 'publie'}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onOpenChange}>Fermer</Button>
          {avis?.statut !== 'publie' && (
            <Button onClick={handleValidate} disabled={isSaving || !reponse.trim()}>
              {isSaving ? <Spinner className="h-4 w-4 mr-2" /> : null}
              Valider et Publier
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────

function ReplyDialog({ message, onOpenChange, onReplied }: {
  message: SocialMessage | null; onOpenChange: () => void; onReplied: () => void;
}) {
  const [contenu, setContenu] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  useEffect(() => setContenu(''), [message]);

  const handleSend = async () => {
    if (!message) return;
    if (!contenu.trim()) { toast.error('Le message ne peut pas être vide'); return; }
    setIsSaving(true);
    try {
      await api.post(`/social/messages/${message.id}/repondre`, { contenu: contenu.trim() });
      toast.success('Réponse envoyée');
      onOpenChange();
      onReplied();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'envoi");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!message} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Répondre</DialogTitle>
          <DialogDescription>{message?.contact_nom || message?.contact_id} — {message?.plateforme}</DialogDescription>
        </DialogHeader>
        {message && (
          <div className="bg-muted rounded-md p-3 text-sm text-muted-foreground">{message.contenu}</div>
        )}
        <div>
          <Label htmlFor="reply">Votre réponse</Label>
          <Textarea id="reply" value={contenu} onChange={(e) => setContenu(e.target.value)} rows={4} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onOpenChange}>Annuler</Button>
          <Button onClick={handleSend} disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Envoyer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NewPostDialog({ open, onOpenChange, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void;
}) {
  const [plateforme, setPlateforme] = useState('whatsapp');
  const [contenu, setContenu] = useState('');
  const [datePublication, setDatePublication] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) { setPlateforme('whatsapp'); setContenu(''); setDatePublication(''); }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contenu.trim()) { toast.error('Le contenu est requis'); return; }
    setIsSaving(true);
    try {
      await api.post('/social/posts', {
        plateforme,
        contenu: contenu.trim(),
        date_publication_prevue: datePublication ? new Date(datePublication).toISOString() : undefined,
      });
      toast.success('Post créé en brouillon');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la création');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau post</DialogTitle>
          <DialogDescription>Créé en brouillon — publiez-le ensuite depuis la liste.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="plateforme">Plateforme</Label>
            <select id="plateforme" value={plateforme} onChange={(e) => setPlateforme(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="tiktok">TikTok</option>
            </select>
          </div>
          <div>
            <Label htmlFor="contenu">Contenu</Label>
            <Textarea id="contenu" value={contenu} onChange={(e) => setContenu(e.target.value)} rows={4} />
          </div>
          <div>
            <Label htmlFor="date-pub">Date de publication (optionnel)</Label>
            <Input id="date-pub" type="datetime-local" value={datePublication} onChange={(e) => setDatePublication(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
