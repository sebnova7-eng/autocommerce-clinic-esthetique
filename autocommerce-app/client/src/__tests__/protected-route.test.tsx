import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/contexts/AuthContext";
import { useLocation } from "wouter";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("wouter", () => ({ useLocation: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseLocation = vi.mocked(useLocation);

const authState = (overrides: Partial<ReturnType<typeof useAuth>> = {}) => ({
  user: null,
  isLoading: false,
  isAuthenticated: false,
  login: vi.fn(),
  verifyMfa: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
  ...overrides,
});

describe("ProtectedRoute — sécurité de navigation", () => {
  beforeEach(() => {
    mockedUseLocation.mockReturnValue(["/private", vi.fn()]);
  });

  it("affiche un état de chargement avant de décider l’accès", () => {
    mockedUseAuth.mockReturnValue(authState({ isLoading: true }));

    render(<ProtectedRoute><div>zone privée</div></ProtectedRoute>);

    expect(screen.queryByText("zone privée")).not.toBeInTheDocument();
    expect(document.querySelector("svg")).toBeInTheDocument();
  });

  it("redirige vers login sans afficher de contenu interne si la session est absente", () => {
    const setLocation = vi.fn();
    mockedUseLocation.mockReturnValue(["/patients", setLocation]);
    mockedUseAuth.mockReturnValue(authState());

    render(<ProtectedRoute><div>données patients</div></ProtectedRoute>);

    expect(setLocation).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("données patients")).not.toBeInTheDocument();
  });

  it.each(["directrice", "admin"])("autorise le rôle %s pour une route d’administration", (role) => {
    mockedUseAuth.mockReturnValue(authState({
      user: { id: 1, email: `${role}@clinic.test`, nom: role, prenom: "User", role },
      isAuthenticated: true,
    }));

    render(<ProtectedRoute requiredRoles={["directrice", "admin"]}><div>administration</div></ProtectedRoute>);

    expect(screen.getByText("administration")).toBeInTheDocument();
  });

  it.each(["medecin", "estheticienne", "assistante", "commercial"])("refuse le rôle %s sur une route d’administration", (role) => {
    mockedUseAuth.mockReturnValue(authState({
      user: { id: 1, email: `${role}@clinic.test`, nom: role, prenom: "User", role },
      isAuthenticated: true,
    }));

    render(<ProtectedRoute requiredRoles={["directrice", "admin"]}><div>administration</div></ProtectedRoute>);

    expect(screen.getByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    expect(screen.queryByText("administration")).not.toBeInTheDocument();
  });

  it("autorise une route authentifiée sans contrainte de rôle explicite", () => {
    mockedUseAuth.mockReturnValue(authState({
      user: { id: 1, email: "assistant@clinic.test", nom: "Assistante", prenom: "A", role: "assistante" },
      isAuthenticated: true,
    }));

    render(<ProtectedRoute><div>agenda interne</div></ProtectedRoute>);

    expect(screen.getByText("agenda interne")).toBeInTheDocument();
  });
});
