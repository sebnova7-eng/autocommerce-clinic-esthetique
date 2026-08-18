import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import {
  authApi,
  clearTokens,
  getAccessToken,
  setAccessToken,
  type UserOut,
} from "@/lib/api";

const user: UserOut = {
  id: 7,
  email: "doctor@clinic.test",
  nom: "Martin",
  prenom: "Ada",
  role: "medecin",
};

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <output data-testid="loading">{String(auth.isLoading)}</output>
      <output data-testid="authenticated">{String(auth.isAuthenticated)}</output>
      <output data-testid="user">{auth.user?.email ?? "none"}</output>
      <button onClick={() => void auth.login("doctor@clinic.test", "correct-password")}>login</button>
      <button onClick={() => void auth.verifyMfa("challenge", "123456")}>verify</button>
      <button onClick={auth.logout}>logout</button>
      <button onClick={() => void auth.refreshUser()}>refresh</button>
    </div>
  );
}

const renderProvider = () => render(<AuthProvider><Probe /></AuthProvider>);

describe("AuthProvider — session et MFA", () => {
  afterEach(() => {
    clearTokens();
    vi.restoreAllMocks();
  });

  it("réhydrate une session valide depuis le token mémoire", async () => {
    setAccessToken("rehydrate-access");
    vi.spyOn(authApi, "me").mockResolvedValue({ data: user } as never);

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("user")).toHaveTextContent(user.email);
    expect(authApi.me).toHaveBeenCalledTimes(1);
  });

  it("efface une session dont la réhydratation échoue", async () => {
    setAccessToken("invalid-access");
    vi.spyOn(authApi, "me").mockRejectedValue(new Error("session expired"));

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(getAccessToken()).toBeNull();
  });

  it("login sans MFA stocke l’access token et charge le profil", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({
      data: { access_token: "login-access", token_type: "bearer", expires_in: 900 },
    } as never);
    vi.spyOn(authApi, "me").mockResolvedValue({ data: user } as never);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    fireEvent.click(screen.getByRole("button", { name: "login" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(getAccessToken()).toBe("login-access");
    expect(authApi.login).toHaveBeenCalledWith("doctor@clinic.test", "correct-password");
    expect(authApi.me).toHaveBeenCalledTimes(1);
  });

  it("login MFA retourne le challenge sans créer de session authentifiée", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({
      data: { mfa_required: true, challenge_token: "challenge-123" },
    } as never);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    fireEvent.click(screen.getByRole("button", { name: "login" }));

    await waitFor(() => expect(authApi.login).toHaveBeenCalled());
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(getAccessToken()).toBeNull();
  });

  it("verifyMfa réussi stocke le token et charge l’utilisateur", async () => {
    vi.spyOn(authApi, "verifyMfa").mockResolvedValue({
      data: { access_token: "mfa-access", token_type: "bearer", expires_in: 900 },
    } as never);
    vi.spyOn(authApi, "me").mockResolvedValue({ data: user } as never);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    fireEvent.click(screen.getByRole("button", { name: "verify" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    expect(authApi.verifyMfa).toHaveBeenCalledWith("challenge", "123456");
    expect(getAccessToken()).toBe("mfa-access");
  });

  it("logout efface immédiatement l’utilisateur et les tokens même si l’API échoue", async () => {
    setAccessToken("logout-access");
    vi.spyOn(authApi, "me").mockResolvedValue({ data: user } as never);
    vi.spyOn(authApi, "logout").mockRejectedValue(new Error("network"));

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    fireEvent.click(screen.getByRole("button", { name: "logout" }));

    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(getAccessToken()).toBeNull();
    expect(authApi.logout).toHaveBeenCalledTimes(1);
  });

  it("refreshUser déconnecte lorsque la session serveur devient invalide", async () => {
    setAccessToken("refresh-user-access");
    const me = vi.spyOn(authApi, "me").mockResolvedValueOnce({ data: user } as never);
    vi.spyOn(authApi, "logout").mockResolvedValue({} as never);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("true"));
    me.mockRejectedValueOnce(new Error("revoked"));
    fireEvent.click(screen.getByRole("button", { name: "refresh" }));

    await waitFor(() => expect(screen.getByTestId("authenticated")).toHaveTextContent("false"));
    expect(getAccessToken()).toBeNull();
    expect(authApi.logout).toHaveBeenCalledTimes(1);
  });
});
