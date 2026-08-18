import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PatientsList from "@/pages/patients/PatientsList";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useLocation } from "wouter";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/components/layout/DashboardLayout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="layout">{children}</div>,
}));
vi.mock("@/components/patients/PatientFormDialog", () => ({
  PatientFormDialog: () => null,
}));
vi.mock("wouter", () => ({ useLocation: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseLocation = vi.mocked(useLocation);

const patient = {
  id: 11,
  nom: "Martin",
  prenom: "Ada",
  telephone: "+216 12 345 678",
  email: "ada@example.test",
  date_inscription: "2030-01-15T10:00:00Z",
};

const authFor = (role: string) => ({
  user: { id: 1, email: `${role}@clinic.test`, nom: role, prenom: "User", role },
  isLoading: false,
  isAuthenticated: true,
  login: vi.fn(),
  verifyMfa: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
});

describe("PatientsList — états métier et RBAC UI", () => {
  beforeEach(() => {
    mockedUseLocation.mockReturnValue(["/patients", vi.fn()]);
    mockedUseAuth.mockReturnValue(authFor("medecin"));
    vi.spyOn(api, "get").mockResolvedValue({ data: [patient] } as never);
  });

  it("affiche loading puis les données patient reçues de l’API", async () => {
    render(<PatientsList />);

    expect(screen.queryByText("Ada")).not.toBeInTheDocument();
    expect(await screen.findByText("Martin")).toBeInTheDocument();
    expect(screen.getByText("+216 12 345 678")).toBeInTheDocument();
    expect(screen.getByText("1 patient(s) enregistré(s)")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/patients");
  });

  it("filtre les patients par nom, prénom ou téléphone", async () => {
    render(<PatientsList />);
    await screen.findByText("Martin");
    const search = screen.getByPlaceholderText("Rechercher par nom, prénom ou téléphone...");

    fireEvent.change(search, { target: { value: "injoignable" } });
    expect(screen.getByText("Aucun patient trouvé")).toBeInTheDocument();

    fireEvent.change(search, { target: { value: "12 345" } });
    expect(screen.getByText("Martin")).toBeInTheDocument();
  });

  it("affiche un état vide et une erreur utilisateur lorsque l’API renvoie 403", async () => {
    vi.spyOn(api, "get").mockRejectedValue({ response: { status: 403, data: { detail: "forbidden" } } });

    render(<PatientsList />);

    await waitFor(() => expect(screen.getByText("Aucun patient trouvé")).toBeInTheDocument());
    expect(toast.error).toHaveBeenCalledWith("Erreur lors du chargement des patients");
  });

  it("réserve l’action d’anonymisation aux rôles directrice et admin", async () => {
    const deleteSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} } as never);
    mockedUseAuth.mockReturnValue(authFor("directrice"));
    render(<PatientsList />);
    await screen.findByText("Martin");

    fireEvent.click(screen.getByRole("button", { name: /Anonymiser/i }));
    expect(screen.getByRole("heading", { name: "Anonymiser ce patient ?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l'anonymisation" }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("/patients/11/rgpd"));
    expect(toast.success).toHaveBeenCalledWith("Patient anonymisé");
  });

  it("ne rend pas le bouton d’anonymisation pour un médecin", async () => {
    mockedUseAuth.mockReturnValue(authFor("medecin"));
    render(<PatientsList />);
    await screen.findByText("Martin");

    expect(screen.queryByRole("button", { name: /Anonymiser/i })).not.toBeInTheDocument();
  });

  it("efface l’ancien état patient lorsqu’un rechargement de session renvoie 403", async () => {
    mockedUseAuth.mockReturnValue(authFor("directrice"));
    const getSpy = vi.spyOn(api, "get")
      .mockResolvedValueOnce({ data: [patient] } as never)
      .mockRejectedValueOnce({ response: { status: 403, data: { detail: "forbidden" } } });
    vi.spyOn(api, "delete").mockResolvedValue({ data: {} } as never);
    render(<PatientsList />);
    await screen.findByText("Martin");

    fireEvent.click(screen.getByRole("button", { name: /Anonymiser/i }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l'anonymisation" }));
    await waitFor(() => expect(getSpy).toHaveBeenCalledTimes(2));

    expect(await screen.findByText("Aucun patient trouvé")).toBeInTheDocument();
    expect(screen.queryByText("Martin")).not.toBeInTheDocument();
  });
});
