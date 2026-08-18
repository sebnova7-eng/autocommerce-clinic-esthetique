import axios, { AxiosError, type AxiosRequestConfig, type AxiosResponse } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  authApi,
  clearTokens,
  getAccessToken,
  getMfaChallengeToken,
  publicApi,
  publicApiClient,
  setAccessToken,
  setMfaChallengeToken,
  clearMfaChallengeToken,
} from "@/lib/api";

const response = (config: AxiosRequestConfig, data: unknown, status = 200): AxiosResponse => ({
  data,
  status,
  statusText: status === 200 ? "OK" : "Error",
  headers: {},
  config: config as AxiosResponse["config"],
});

describe("API frontend — frontières et tokens", () => {
  afterEach(() => {
    clearTokens();
    clearMfaChallengeToken();
    vi.restoreAllMocks();
  });

  it("conserve access token et challenge MFA uniquement en mémoire", () => {
    setAccessToken("access-memory");
    setMfaChallengeToken("challenge-memory");

    expect(getAccessToken()).toBe("access-memory");
    expect(getMfaChallengeToken()).toBe("challenge-memory");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);

    clearTokens();
    clearMfaChallengeToken();
    expect(getAccessToken()).toBeNull();
    expect(getMfaChallengeToken()).toBeNull();
  });

  it("ajoute le Bearer en mémoire aux appels privés sans persister le token", async () => {
    setAccessToken("private-access");
    let seenConfig: AxiosRequestConfig | undefined;
    api.defaults.adapter = async (config) => {
      seenConfig = config;
      return response(config, { ok: true });
    };

    await api.get("/patients");

    expect(seenConfig?.baseURL).toBe("/api/private");
    expect(seenConfig?.headers?.Authorization).toBe("Bearer private-access");
    expect(window.localStorage.getItem("access_token")).toBeNull();
    expect(window.sessionStorage.getItem("access_token")).toBeNull();
  });

  it("ne joint jamais le token aux appels Public Gateway", async () => {
    setAccessToken("must-not-cross-public-boundary");
    let seenConfig: AxiosRequestConfig | undefined;
    publicApiClient.defaults.adapter = async (config) => {
      seenConfig = config;
      return response(config, []);
    };

    await publicApi.getPraticiens();

    expect(seenConfig?.baseURL).toBe("/api/public");
    expect(seenConfig?.withCredentials).toBe(false);
    expect(seenConfig?.headers?.Authorization).toBeUndefined();
  });

  it("rafraîchit une session expirée puis rejoue la requête privée", async () => {
    setAccessToken("expired-access");
    let privateCalls = 0;
    let retriedConfig: AxiosRequestConfig | undefined;
    api.defaults.adapter = async (config) => {
      privateCalls += 1;
      if (privateCalls === 1) {
        return Promise.reject(new AxiosError(
          "Unauthorized",
          "ERR_BAD_REQUEST",
          config,
          undefined,
          response(config, { detail: "expired" }, 401),
        ));
      }
      retriedConfig = config;
      return response(config, { patients: [] });
    };
    vi.spyOn(axios, "post").mockResolvedValue({ data: { access_token: "refreshed-access" } } as AxiosResponse);

    const result = await api.get("/patients");

    expect(result.data).toEqual({ patients: [] });
    expect(privateCalls).toBe(2);
    expect(axios.post).toHaveBeenCalledWith("/api/private/auth/refresh", undefined, { withCredentials: true });
    expect(retriedConfig?.headers?.Authorization).toBe("Bearer refreshed-access");
    expect(getAccessToken()).toBe("refreshed-access");
  });

  it("ne tente pas un refresh sur les endpoints d’authentification", async () => {
    const config: AxiosRequestConfig = { url: "/auth/login", method: "post" };
    api.defaults.adapter = async (request) => Promise.reject(new AxiosError(
      "Unauthorized",
      "ERR_BAD_REQUEST",
      request,
      undefined,
      response(request, { detail: "invalid" }, 401),
    ));
    const refreshSpy = vi.spyOn(axios, "post");

    await expect(authApi.login("user@example.com", "wrong-password")).rejects.toBeInstanceOf(AxiosError);

    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it("laisse une réponse 403 remonter au consommateur pour que l’UI l’affiche", async () => {
    api.defaults.adapter = async (config) => Promise.reject(new AxiosError(
      "Forbidden",
      "ERR_BAD_REQUEST",
      config,
      undefined,
      response(config, { detail: "forbidden" }, 403),
    ));

    await expect(api.get("/patients/other-clinic")).rejects.toMatchObject({
      response: { status: 403, data: { detail: "forbidden" } },
    });
  });
});
