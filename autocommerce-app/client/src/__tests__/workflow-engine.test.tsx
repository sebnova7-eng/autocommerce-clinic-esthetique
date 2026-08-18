import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkflowEngine from "@/pages/workflow/WorkflowEngine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/components/layout/DashboardLayout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockedUseAuth = vi.mocked(useAuth);

const workflow = {
  id: 3,
  nom: "Rappel post-opératoire",
  description: "Relance après acte",
  trigger_type: "appointment_completed",
  enabled: true,
  status: "active",
  created_at: "2030-01-15T10:00:00Z",
};

const stats = {
  total_executions: 20,
  completed: 18,
  failed: 2,
  drafts_awaiting_approval: 1,
  success_rate: 90,
};

const auth = {
  user: { id: 1, email: "admin@clinic.test", nom: "Admin", prenom: "A", role: "admin" },
  isLoading: false,
  isAuthenticated: true,
  login: vi.fn(),
  verifyMfa: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
};

describe("WorkflowEngine — états et actions", () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue(auth);
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url === "/workflows/") return Promise.resolve({ data: { data: [workflow] } }) as never;
      return Promise.resolve({ data: { data: stats } }) as never;
    });
  });

  it("affiche les workflows et les statistiques après chargement", async () => {
    render(<WorkflowEngine />);

    expect(await screen.findByText("Rappel post-opératoire")).toBeInTheDocument();
    expect(screen.getByText("90.0%")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("exécute un workflow puis recharge la liste", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { status: "queued" } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/3/execute"));
    expect(api.get).toHaveBeenCalledWith("/workflows/");
  });

  it("supprime seulement après confirmation utilisateur", async () => {
    const deleteSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} } as never);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(deleteSpy).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("/workflows/3"));
  });

  it("affiche l’erreur API au lieu de présenter un workflow comme disponible", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("forbidden"));
    render(<WorkflowEngine />);

    expect(await screen.findByText("forbidden")).toBeInTheDocument();
  });
});
