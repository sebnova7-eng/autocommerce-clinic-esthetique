import { describe, expect, it, vi } from "vitest";
import {
  api,
  dossierMedicalApi,
  equipeApi,
  scribeIaApi,
  settingsApi,
} from "@/lib/api";

describe("services API frontend — contrats métier sensibles", () => {
  it("scoppe les appels dossier médical sur l’identifiant patient", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue({ data: [] } as never);
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);

    await dossierMedicalApi.getTimeline(42);
    await dossierMedicalApi.listConsentements(42);
    await dossierMedicalApi.listPhotos(42);
    await dossierMedicalApi.create(42, { praticien_id: 7, date_acte: "2030-01-15" });
    await dossierMedicalApi.signConsentement(42, { signature_base64: "signature" });

    expect(getSpy).toHaveBeenCalledWith("/patients/42/dossiers");
    expect(getSpy).toHaveBeenCalledWith("/patients/42/consentements");
    expect(getSpy).toHaveBeenCalledWith("/patients/42/photos");
    expect(postSpy).toHaveBeenCalledWith("/patients/42/dossiers", { praticien_id: 7, date_acte: "2030-01-15" });
    expect(postSpy).toHaveBeenCalledWith("/patients/42/consentements", { signature_base64: "signature" });
  });

  it("transmet les données IA avec le patient et le dossier explicites", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { text: "ok" } } as never);
    const audio = new Blob(["audio"], { type: "audio/webm" });

    await scribeIaApi.transcribe(audio);
    await scribeIaApi.process(42, "transcription clinique", 99);

    expect(postSpy.mock.calls[0]?.[0]).toBe("/scribe-ia/transcribe");
    expect(postSpy.mock.calls[0]?.[2]).toMatchObject({ headers: { "Content-Type": "multipart/form-data" } });
    expect(postSpy).toHaveBeenCalledWith("/scribe-ia/process", {
      patient_id: 42,
      dossier_id: 99,
      transcription_brute: "transcription clinique",
    });
  });

  it("reste sur les routes privées pour la messagerie d’équipe et ses erreurs", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue({ data: [] } as never);
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
    const putSpy = vi.spyOn(api, "put").mockResolvedValue({ data: {} } as never);
    const deleteSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} } as never);

    await equipeApi.getInbox();
    await equipeApi.getSent(2, 10);
    await equipeApi.send({ destinataire_id: 2, sujet: "Suivi", contenu: "Message" });
    await equipeApi.markRead(3);
    await equipeApi.delete(3);

    expect(getSpy).toHaveBeenCalledWith("/equipe/messages", { params: { page: 1, page_size: 20 } });
    expect(getSpy).toHaveBeenCalledWith("/equipe/messages/sent", { params: { page: 2, page_size: 10 } });
    expect(postSpy).toHaveBeenCalledWith("/equipe/messages", { destinataire_id: 2, sujet: "Suivi", contenu: "Message" });
    expect(putSpy).toHaveBeenCalledWith("/equipe/messages/3/lu");
    expect(deleteSpy).toHaveBeenCalledWith("/equipe/messages/3");
  });

  it("normalise les URLs de branding relatives sans toucher aux URLs absolues", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        nom_clinique: "Clinique",
        couleur_primaire: "#111111",
        couleur_secondaire: "#222222",
        logo_url: "/uploads/logo.png",
      },
    } as never);

    const result = await settingsApi.getBranding();

    expect(result.data.logo_url).toBe("/uploads/logo.png");
  });
});
