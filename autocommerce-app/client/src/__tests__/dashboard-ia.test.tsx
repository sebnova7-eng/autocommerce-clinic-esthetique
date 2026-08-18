import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardIA from "@/pages/dashboard/DashboardIA";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/components/layout/DashboardLayout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mocked(useAuth).mockReturnValue({
  user: { id: 1, email: "doctor@clinic.test", nom: "Martin", prenom: "Ada", role: "medecin" },
  isLoading: false,
  isAuthenticated: true,
  login: vi.fn(),
  verifyMfa: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
});

const baseData = {
  timestamp: "2030-01-15T10:00:00Z",
  daily_summary: { rdvs_today: 4, rdvs_tomorrow: 2, revenue_today: 1200, unpaid_invoices: 1, stock_alerts: 2 },
  absent_patients: { total_absent_patients: 0, patients: [] },
  vip_patients: { total_vip: 1, patients: [{ id: 1, nom: "Ada Martin", points: 200, niveau: "vip", total_ca: 5000 }] },
  ai_recommendations: { recommendations: [{ message: "Rappeler le patient", priority: "high", products: ["Soin A"] }] },
  revenue_forecast: {},
  practitioner_performance: { practitioners: [] },
  cancellation_risk: { clinic_baseline_risk: 0.12, historical_appointments: 100, appointments: [] },
  widgets_config: {},
};

describe("DashboardIA — affichage contrôlé des données IA", () => {
  it("affiche les recommandations et ne montre pas de données médicales non présentes", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { data: baseData } } as never);

    render(<DashboardIA />);

    expect(await screen.findByText("Dashboard IA")).toBeInTheDocument();
    expect(screen.getByText("Rappeler le patient")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("Ada Martin")).toBeInTheDocument();
    expect(screen.getByText("Aucun rendez-vous à risque dans les 30 prochains jours.")).toBeInTheDocument();
  });

  it("affiche un état vide explicite si l’API ne renvoie pas de data", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: {} } as never);

    render(<DashboardIA />);

    expect(await screen.findByText("Aucune donnée disponible")).toBeInTheDocument();
  });

  it("affiche l’erreur API sans présenter le dashboard comme valide", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("forbidden"));

    render(<DashboardIA />);

    expect(await screen.findByText("forbidden")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard IA")).not.toBeInTheDocument();
  });
});
