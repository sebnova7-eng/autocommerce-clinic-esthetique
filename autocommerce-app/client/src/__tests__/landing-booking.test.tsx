import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LandingPage from "@/pages/public/LandingPage";
import { useBranding } from "@/contexts/BrandingContext";
import { publicApi } from "@/lib/api";
import { toast } from "sonner";

vi.mock("@/contexts/BrandingContext", () => ({ useBranding: vi.fn() }));
vi.mock("@/components/LanguageSwitcher", () => ({ default: () => <div aria-label="language-switcher" /> }));

const mockedUseBranding = vi.mocked(useBranding);

const praticien = {
  id: 4,
  nom: "Martin",
  prenom: "Ada",
  nom_complet: "Dr Ada Martin",
  specialite: "Médecine esthétique",
};

const acte = {
  id: 9,
  nom: "Consultation esthétique",
  categorie: "consultation",
  duree_minutes: 45,
  description: "Évaluation initiale",
};

const slot = { heure: "10:30", datetime: "2030-06-15T10:30:00" };

const renderLanding = () => render(<LandingPage />);

describe("LandingPage — Public Gateway et BookingRequest", () => {
  beforeEach(() => {
    mockedUseBranding.mockReturnValue({
      branding: {
        nom_clinique: "Clinique Test",
        couleur_primaire: "#111111",
        couleur_secondaire: "#222222",
        contenu_landing: {
          titre: "Bienvenue",
          services_mis_en_avant: ["Consultation esthétique"],
          adresse: "1 rue du Test",
        },
      },
      isLoading: false,
      applyTheme: vi.fn(),
    });
    vi.spyOn(publicApi, "getPraticiens").mockResolvedValue({ data: [praticien] } as never);
    vi.spyOn(publicApi, "getActes").mockResolvedValue({ data: [acte] } as never);
    vi.spyOn(publicApi, "getDisponibilites").mockResolvedValue({
      data: { praticien_id: praticien.id, date: "2030-06-15", duree_minutes: 45, creneaux: [slot] },
    } as never);
  });

  it("charge uniquement les données publiques prévues et affiche le formulaire après bootstrap", async () => {
    renderLanding();

    expect(await screen.findByText("Réserver un rendez-vous")).toBeInTheDocument();
    expect(screen.getByLabelText("Praticien")).toHaveDisplayValue("Sélectionner un praticien");
    expect(screen.getByText("Dr Ada Martin")).toBeInTheDocument();
    expect(screen.getByText("Consultation esthétique")).toBeInTheDocument();
    expect(publicApi.getPraticiens).toHaveBeenCalledTimes(1);
    expect(publicApi.getActes).toHaveBeenCalledTimes(1);
  });

  it("recharge les disponibilités lorsque le praticien et l’acte sont sélectionnés", async () => {
    renderLanding();
    await screen.findByText("Réserver un rendez-vous");

    fireEvent.change(screen.getByLabelText("Praticien"), { target: { value: String(praticien.id) } });
    fireEvent.change(screen.getByLabelText("Acte"), { target: { value: String(acte.id) } });

    await waitFor(() => expect(publicApi.getDisponibilites).toHaveBeenCalled());
    expect(await screen.findByText("10:30")).toBeInTheDocument();
  });

  it("bloque une réservation avec un téléphone invalide avant l’appel API", async () => {
    const reserveRdv = vi.spyOn(publicApi, "reserveRdv");
    renderLanding();
    await screen.findByText("Réserver un rendez-vous");
    fireEvent.change(screen.getByLabelText("Prénom"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "Martin" } });
    fireEvent.change(screen.getByLabelText("Téléphone"), { target: { value: "123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Réserver" }).closest("form") as HTMLFormElement);

    expect(toast.error).toHaveBeenCalledWith("Format de téléphone invalide");
    expect(reserveRdv).not.toHaveBeenCalled();
  });

  it("envoie une réservation publique avec les données sélectionnées", async () => {
    const reserveRdv = vi.spyOn(publicApi, "reserveRdv").mockResolvedValue({ data: { status: "pending" } } as never);
    renderLanding();
    await screen.findByText("Réserver un rendez-vous");

    fireEvent.change(screen.getByLabelText("Prénom"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "Martin" } });
    fireEvent.change(screen.getByLabelText("Téléphone"), { target: { value: "+216 12 345 678" } });
    fireEvent.change(screen.getByLabelText("Praticien"), { target: { value: String(praticien.id) } });
    fireEvent.change(screen.getByLabelText("Acte"), { target: { value: String(acte.id) } });
    await screen.findByText("10:30");
    fireEvent.change(screen.getByLabelText("Créneau disponible"), { target: { value: slot.datetime } });
    fireEvent.click(screen.getByRole("button", { name: "Réserver" }));

    await waitFor(() => expect(reserveRdv).toHaveBeenCalledWith({
      nom: "Martin",
      prenom: "Ada",
      telephone: "+216 12 345 678",
      praticien_id: 4,
      acte_id: 9,
      date_heure: slot.datetime,
    }));
    expect(toast.success).toHaveBeenCalledWith("Rendez-vous réservé avec succès");
  });

  it("affiche le refus rate-limit du backend sans prétendre que la réservation est créée", async () => {
    const reserveRdv = vi.spyOn(publicApi, "reserveRdv").mockRejectedValue({ response: { status: 429 } });
    renderLanding();
    await screen.findByText("Réserver un rendez-vous");

    fireEvent.change(screen.getByLabelText("Prénom"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "Martin" } });
    fireEvent.change(screen.getByLabelText("Téléphone"), { target: { value: "+216 12 345 678" } });
    fireEvent.change(screen.getByLabelText("Praticien"), { target: { value: String(praticien.id) } });
    fireEvent.change(screen.getByLabelText("Acte"), { target: { value: String(acte.id) } });
    await screen.findByText("10:30");
    fireEvent.change(screen.getByLabelText("Créneau disponible"), { target: { value: slot.datetime } });
    fireEvent.click(screen.getByRole("button", { name: "Réserver" }));

    await waitFor(() => expect(reserveRdv).toHaveBeenCalled());
    expect(toast.error).toHaveBeenCalledWith("Trop de tentatives. Réessayez dans une minute.");
    expect(toast.success).not.toHaveBeenCalled();
  });
});
