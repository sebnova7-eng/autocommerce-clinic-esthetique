import React, { useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader, IScannerControls } from '@zxing/browser';
import { NotFoundException } from '@zxing/library';
import { Button } from '@/components/ui/button';
import { Camera, CameraOff, AlertCircle } from 'lucide-react';

interface BarcodeCameraScannerProps {
  /** Appelé avec le texte décodé (QR JSON ou numéro de code-barres brut). */
  onDetected: (code: string) => void;
  /** Format d'affichage : plein cadre (page dédiée) ou compact (inline dans une carte). */
  compact?: boolean;
}

/**
 * Scanner caméra réel — code-barres (Code 128, EAN...) et QR code.
 *
 * Utilise ZXing plutôt que l'API native BarcodeDetector : cette dernière
 * n'est pas disponible sur Safari/iOS, alors que la clinique a
 * explicitement besoin que ça marche depuis un téléphone (éviter l'achat
 * d'une douchette USB comme frein à la vente). ZXing fonctionne partout
 * où getUserMedia fonctionne, iOS inclus.
 *
 * Nécessite HTTPS (ou localhost) — getUserMedia est bloqué sur http://
 * par tous les navigateurs modernes, à garder en tête pour le déploiement.
 */
export function BarcodeCameraScanner({ onDetected, compact = false }: BarcodeCameraScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const lastCodeRef = useRef<{ code: string; at: number } | null>(null);

  const [isActive, setIsActive] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string | undefined>(undefined);

  useEffect(() => {
    return () => {
      controlsRef.current?.stop();
    };
  }, []);

  const listCameras = async () => {
    try {
      const cams = await BrowserMultiFormatReader.listVideoInputDevices();
      setDevices(cams);
      // Préfère la caméra arrière ("environment") sur mobile — c'est
      // celle qu'on utilise naturellement pour scanner un objet.
      const back = cams.find((d) => /back|rear|environment/i.test(d.label));
      setDeviceId((back || cams[cams.length - 1])?.deviceId);
    } catch {
      // Énumération avant permission accordée peut échouer sur certains
      // navigateurs — pas bloquant, on retente après le premier accès.
    }
  };

  useEffect(() => {
    listCameras();
  }, []);

  const start = async () => {
    setError(null);
    setIsStarting(true);
    if (!readerRef.current) {
      readerRef.current = new BrowserMultiFormatReader();
    }
    try {
      const controls = await readerRef.current.decodeFromVideoDevice(
        deviceId,
        videoRef.current!,
        (result, err) => {
          if (result) {
            const code = result.getText();
            const now = Date.now();
            // Anti-doublon : la même image reste souvent décodée plusieurs
            // fois par seconde tant que l'objet est dans le cadre.
            if (lastCodeRef.current?.code === code && now - lastCodeRef.current.at < 3000) {
              return;
            }
            lastCodeRef.current = { code, at: now };
            onDetected(code);
          }
          if (err && !(err instanceof NotFoundException)) {
            // NotFoundException = "rien dans le cadre pour l'instant", normal à chaque frame.
            // Toute autre erreur est réelle et vaut la peine d'être surfacée.
            console.error('Erreur de scan caméra:', err);
          }
        }
      );
      controlsRef.current = controls;
      setIsActive(true);
      await listCameras(); // les labels ne sont dispos qu'après la permission accordée
    } catch (e: any) {
      let message = "Impossible d'accéder à la caméra.";
      if (e?.name === 'NotAllowedError') {
        message = "Accès caméra refusé. Autorisez la caméra dans les paramètres du navigateur.";
      } else if (e?.name === 'NotFoundError') {
        message = 'Aucune caméra détectée sur cet appareil.';
      } else if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        message = 'Le scan caméra nécessite une connexion HTTPS.';
      }
      setError(message);
      setIsActive(false);
    } finally {
      setIsStarting(false);
    }
  };

  const stop = () => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    setIsActive(false);
  };

  const toggle = () => {
    if (isActive) stop();
    else start();
  };

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant={isActive ? 'destructive' : 'default'}
        onClick={toggle}
        disabled={isStarting}
        className="w-full sm:w-auto"
      >
        {isActive ? <CameraOff className="w-4 h-4 mr-2" /> : <Camera className="w-4 h-4 mr-2" />}
        {isStarting ? 'Démarrage...' : isActive ? 'Arrêter la caméra' : 'Scanner avec la caméra'}
      </Button>

      {devices.length > 1 && isActive && (
        <select
          value={deviceId}
          onChange={(e) => { setDeviceId(e.target.value); stop(); }}
          className="w-full h-9 px-3 border rounded-md text-sm"
        >
          {devices.map((d) => (
            <option key={d.deviceId} value={d.deviceId}>{d.label || 'Caméra'}</option>
          ))}
        </select>
      )}

      {error && (
        <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 rounded-md p-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div
        className={`relative overflow-hidden rounded-md bg-black ${isActive ? '' : 'hidden'} ${compact ? 'aspect-video max-h-48' : 'aspect-video'}`}
      >
        <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
        {isActive && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-2/3 h-2/3 border-2 border-white/70 rounded-lg" />
          </div>
        )}
      </div>
    </div>
  );
}
