import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "@/pages/auth/Login";
import MfaVerification from "@/pages/auth/MfaVerification";
import { useAuth } from "@/contexts/AuthContext";
import { useBranding } from "@/contexts/BrandingContext";
import {
  clearMfaChallengeToken,
  getMfaChallengeToken,
  setMfaChallengeToken,
} from "@/lib/api";
import { toast } from "sonner";
import { useLocation } from "wouter";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/contexts/BrandingContext", () => ({ useBranding: vi.fn() }));
vi.mock("wouter", () => ({ useLocation: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseBranding = vi.mocked(useBranding);
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

describe("pages d’authentification", () => {
  beforeEach(() => {
    mockedUseBranding.mockReturnValue({ branding: { nom_clinique: "Clinique Test", couleur_primaire: "#111111", couleur_secondaire: "#222222" }, isLoading: false, applyTheme: vi.fn() });
    mockedUseLocation.mockReturnValue(["/login", vi.fn()]);
    clearMfaChallengeToken();
  });

  it("redirige vers le dashboard après un login sans MFA", async () => {
    const setLocation = vi.fn();
    const login = vi.fn().mockResolvedValue({ requiresMfa: false });
    mockedUseLocation.mockReturnValue(["/login", setLocation]);
    mockedUseAuth.mockReturnValue(authState({ login }));

    render(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@clinic.test" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "a-secure-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(setLocation).toHaveBeenCalledWith("/dashboard"));
    expect(login).toHaveBeenCalledWith("user@clinic.test", "a-secure-password");
  });

  it("stocke le challenge MFA en mémoire puis redirige vers la vérification", async () => {
    const setLocation = vi.fn();
    const login = vi.fn().mockResolvedValue({ requiresMfa: true, challengeToken: "challenge-from-login" });
    mockedUseLocation.mockReturnValue(["/login", setLocation]);
    mockedUseAuth.mockReturnValue(authState({ login }));

    render(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "mfa@clinic.test" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "a-secure-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(setLocation).toHaveBeenCalledWith("/mfa-verify"));
    expect(getMfaChallengeToken()).toBe("challenge-from-login");
    expect(window.sessionStorage.length).toBe(0);
  });

  it("affiche le message de rate limit renvoyé par le backend", async () => {
    const login = vi.fn().mockRejectedValue({ response: { status: 429 } });
    mockedUseAuth.mockReturnValue(authState({ login }));

    render(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@clinic.test" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "bad-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Trop de tentatives. Réessayez dans une minute.")).toBeInTheDocument();
  });

  it("redirige vers login si le challenge MFA est absent ou expiré", async () => {
    const setLocation = vi.fn();
    mockedUseLocation.mockReturnValue(["/mfa-verify", setLocation]);
    mockedUseAuth.mockReturnValue(authState());

    render(<MfaVerification />);

    await waitFor(() => expect(setLocation).toHaveBeenCalledWith("/login"));
    expect(toast.error).toHaveBeenCalledWith("Session expirée, veuillez vous reconnecter");
  });

  it("refuse un OTP qui ne contient pas six chiffres", async () => {
    setMfaChallengeToken("challenge-present");
    const verifyMfa = vi.fn();
    mockedUseAuth.mockReturnValue(authState({ verifyMfa }));

    render(<MfaVerification />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Vérifier" }).closest("form") as HTMLFormElement);

    expect(await screen.findByText("Le code doit contenir 6 chiffres")).toBeInTheDocument();
    expect(verifyMfa).not.toHaveBeenCalled();
  });

  it("vérifie un OTP valide, nettoie le challenge et ouvre le dashboard", async () => {
    setMfaChallengeToken("challenge-present");
    const setLocation = vi.fn();
    const verifyMfa = vi.fn().mockResolvedValue(undefined);
    mockedUseLocation.mockReturnValue(["/mfa-verify", setLocation]);
    mockedUseAuth.mockReturnValue(authState({ verifyMfa }));

    render(<MfaVerification />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Vérifier" }));

    await waitFor(() => expect(setLocation).toHaveBeenCalledWith("/dashboard"));
    expect(verifyMfa).toHaveBeenCalledWith("challenge-present", "123456");
    expect(getMfaChallengeToken()).toBeNull();
  });

  it("affiche le verrouillage temporaire quand le MFA renvoie 429", async () => {
    setMfaChallengeToken("challenge-present");
    const verifyMfa = vi.fn().mockRejectedValue({ response: { status: 429 } });
    mockedUseAuth.mockReturnValue(authState({ verifyMfa }));

    render(<MfaVerification />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Vérifier" }));

    expect(await screen.findByText("Trop de tentatives. Compte verrouillé temporairement.")).toBeInTheDocument();
  });
});
