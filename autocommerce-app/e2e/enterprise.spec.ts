import { expect, test, type Page } from '@playwright/test';
import crypto from 'node:crypto';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@clinic.local';
const CLINIC_B_EMAIL = process.env.E2E_CLINIC_B_EMAIL || 'admin@clinic-b.local';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const CLINIC_B_PASSWORD = process.env.E2E_CLINIC_B_PASSWORD || process.env.QA_CLINIC_B_PASSWORD;
const MFA_SECRET = process.env.E2E_MFA_SECRET;
const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1';

function assertCredentials(): void {
  if (!ADMIN_PASSWORD || !CLINIC_B_PASSWORD) {
    throw new Error('E2E_ADMIN_PASSWORD and E2E_CLINIC_B_PASSWORD/QA_CLINIC_B_PASSWORD must be injected outside the repository');
  }
}

async function apiJson(
  page: Page,
  token: string | undefined,
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<{ status: number; body: any; headers: Record<string, string> }> {
  return page.evaluate(async ({ path, token, method, body }) => {
    const headers = new Headers({ Accept: 'application/json' });
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (body !== undefined) headers.set('Content-Type', 'application/json');
    const response = await fetch(path, {
      method: method || 'GET',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let parsed: unknown = text;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      // Preserve non-JSON body for diagnostics without logging secrets.
    }
    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });
    return { status: response.status, body: parsed, headers: responseHeaders };
  }, { path, token, method: options.method, body: options.body });
}

async function loginThroughUi(page: Page, email: string, password: string): Promise<string> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await page.goto('/login');
    await expect(page.getByText('Connectez-vous à votre compte')).toBeVisible();
    const loginResponse = page.waitForResponse((response) => (
      response.url().includes('/api/private/auth/login') && response.request().method() === 'POST'
    ));
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Mot de passe').fill(password);
    await page.getByRole('button', { name: 'Se connecter' }).click();
    const response = await loginResponse;
    if (response.status() === 429 && attempt === 0) {
      const retryAfter = Number(response.headers()['retry-after'] || '60');
      await page.waitForTimeout((Math.max(1, retryAfter) + 1) * 1000);
      continue;
    }
    expect(response.status()).toBe(200);
    const payload = await response.json();
  if (payload.mfa_required) {
    if (!MFA_SECRET) {
      throw new Error('MFA is enabled; inject E2E_MFA_SECRET outside the repository for browser E2E');
    }
    await expect(page).toHaveURL(/\/mfa-verify$/);
    const verifyResponse = page.waitForResponse((verify) => (
      verify.url().includes('/api/private/auth/mfa/verify') && verify.request().method() === 'POST'
    ));
    await page.locator('input[autocomplete="one-time-code"]').fill(totp(MFA_SECRET));
    await page.getByRole('button', { name: 'Vérifier' }).click();
    const verified = await verifyResponse;
    expect(verified.status()).toBe(200);
    const verifiedPayload = await verified.json();
    expect(verifiedPayload.access_token).toBeTruthy();
    await expect(page).toHaveURL(/\/dashboard$/);
    return verifiedPayload.access_token as string;
  }
    expect(payload.access_token).toBeTruthy();
    await expect(page).toHaveURL(/\/dashboard$/);
    return payload.access_token as string;
  }
  throw new Error('Login rate limit did not clear within the E2E retry window');
}

async function storageTokenKeys(page: Page): Promise<string[]> {
  return page.evaluate(() => [
    ...Object.keys(localStorage),
    ...Object.keys(sessionStorage),
  ].filter((key) => /token|jwt|auth|refresh|access/i.test(key)));
}

function totp(secret: string, timestamp = Date.now()): string {
  const normalized = secret.replace(/\s+/g, '').replace(/=/g, '').toUpperCase();
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const character of normalized) {
    const index = alphabet.indexOf(character);
    if (index >= 0) bits += index.toString(2).padStart(5, '0');
  }
  const bytes = Buffer.alloc(Math.floor(bits.length / 8));
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = parseInt(bits.slice(index * 8, index * 8 + 8), 2);
  }
  const counter = Math.floor(timestamp / 1000 / 30);
  const counterBuffer = Buffer.alloc(8);
  counterBuffer.writeBigUInt64BE(BigInt(counter));
  const digest = crypto.createHmac('sha1', bytes).update(counterBuffer).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const value = (
    ((digest[offset] & 0x7f) << 24)
    | (digest[offset + 1] << 16)
    | (digest[offset + 2] << 8)
    | digest[offset + 3]
  ) % 1_000_000;
  return value.toString().padStart(6, '0');
}

test.beforeEach(async () => {
  assertCredentials();
});

test('authentification, refresh HttpOnly, logout/revocation and storage hygiene', async ({ page }) => {
  const accessToken = await loginThroughUi(page, ADMIN_EMAIL, ADMIN_PASSWORD!);
  const cookiesBefore = await page.context().cookies();
  const refreshBefore = cookiesBefore.find((cookie) => cookie.name === 'autocommerce_refresh');
  expect(refreshBefore?.httpOnly).toBeTruthy();
  expect(await storageTokenKeys(page)).toEqual([]);

  const refresh = await apiJson(page, accessToken, '/api/private/auth/refresh', { method: 'POST' });
  expect(refresh.status).toBe(200);
  const cookiesAfter = await page.context().cookies();
  const refreshAfter = cookiesAfter.find((cookie) => cookie.name === 'autocommerce_refresh');
  expect(refreshAfter?.httpOnly).toBeTruthy();
  expect(refreshAfter?.value).toBeTruthy();
  expect(refreshAfter?.value).not.toBe(refreshBefore?.value);
  expect(await storageTokenKeys(page)).toEqual([]);

  await page.getByRole('button', { name: ADMIN_EMAIL }).click();
  await page.getByText('Déconnexion', { exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  const afterLogout = await apiJson(page, undefined, '/api/private/auth/refresh', { method: 'POST' });
  expect(afterLogout.status).toBe(401);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  expect(await storageTokenKeys(page)).toEqual([]);
});

test('MFA setup/confirm/verify is exercised when staging account is not already enabled', async ({ page }) => {
  const initialToken = await loginThroughUi(page, ADMIN_EMAIL, ADMIN_PASSWORD!);
  const status = await apiJson(page, initialToken, '/api/private/auth/mfa/status');
  expect(status.status).toBe(200);
  if (status.body?.enabled && !MFA_SECRET) {
    test.skip(true, 'MFA already enabled; inject E2E_MFA_SECRET for a non-mutating verification run');
    return;
  }

  let secret = MFA_SECRET;
  if (!status.body?.enabled) {
    const setup = await apiJson(page, initialToken, '/api/private/auth/mfa/setup', { method: 'POST' });
    expect(setup.status).toBe(200);
    expect(setup.body?.secret).toBeTruthy();
    secret = setup.body.secret as string;
    const confirm = await apiJson(page, initialToken, '/api/private/auth/mfa/confirm', {
      method: 'POST',
      body: { otp: totp(secret) },
    });
    expect(confirm.status).toBe(200);
    expect(confirm.body?.mfa_enabled).toBe(true);
    await apiJson(page, initialToken, '/api/private/auth/logout', { method: 'POST' });
  }

  await page.goto('/login');
  const mfaLogin = page.waitForResponse((response) => (
    response.url().includes('/api/private/auth/login') && response.request().method() === 'POST'
  ));
  await page.getByLabel('Email').fill(ADMIN_EMAIL);
  await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD!);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  const mfaLoginResponse = await mfaLogin;
  expect(mfaLoginResponse.status()).toBe(200);
  const challenge = await mfaLoginResponse.json();
  expect(challenge.mfa_required).toBe(true);
  await expect(page).toHaveURL(/\/mfa-verify$/);
  const verifyResponse = page.waitForResponse((response) => (
    response.url().includes('/api/private/auth/mfa/verify') && response.request().method() === 'POST'
  ));
  await page.locator('input[autocomplete="one-time-code"]').fill(totp(secret!));
  await page.getByRole('button', { name: 'Vérifier' }).click();
  const verified = await verifyResponse;
  expect(verified.status()).toBe(200);
  const verifiedPayload = await verified.json();
  expect(verifiedPayload.access_token).toBeTruthy();
  await expect(page).toHaveURL(/\/dashboard$/);
  const verifiedToken = verifiedPayload.access_token as string;
  const verifiedStatus = await apiJson(page, verifiedToken, '/api/private/auth/mfa/status');
  expect(verifiedStatus.status).toBe(200);
  expect(verifiedStatus.body?.enabled).toBe(true);

  const disable = await apiJson(page, verifiedToken, '/api/private/auth/mfa/disable', {
    method: 'POST',
    body: { password: ADMIN_PASSWORD },
  });
  expect(disable.status).toBe(200);
  expect(disable.body?.mfa_enabled).toBe(false);
});

test('Clinic A/B IDOR, public/private boundary and no cross-tenant response data', async ({ page, browser }) => {
  test.setTimeout(120_000);
  const adminToken = await loginThroughUi(page, ADMIN_EMAIL, ADMIN_PASSWORD!);
  const ownPatients = await apiJson(page, adminToken, '/api/private/patients');
  expect(ownPatients.status).toBe(200);
  const patientA = ownPatients.body?.[0];
  expect(patientA?.id).toBeTruthy();

  const crossTenant = await apiJson(page, adminToken, '/api/private/patients/2');
  expect([403, 404]).toContain(crossTenant.status);
  const clientTenantOverride = await apiJson(page, adminToken, '/api/private/patients?clinic_id=2');
  expect(clientTenantOverride.status).toBe(200);
  expect(JSON.stringify(clientTenantOverride.body)).not.toContain('patient-b@example.com');

  const clinicBContext = await browser.newContext({ baseURL: BASE_URL });
  const clinicBPage = await clinicBContext.newPage();
  const clinicBToken = await loginThroughUi(clinicBPage, CLINIC_B_EMAIL, CLINIC_B_PASSWORD!);
  const ownB = await apiJson(clinicBPage, clinicBToken, '/api/private/patients/2');
  expect(ownB.status).toBe(200);
  await clinicBContext.close();

  const anonymousContext = await browser.newContext({ baseURL: BASE_URL });
  const anonymousPage = await anonymousContext.newPage();
  await anonymousPage.goto('/');
  const privateAnonymous = await apiJson(anonymousPage, undefined, '/api/private/patients');
  expect(privateAnonymous.status).toBe(401);
  const publicMedical = await apiJson(anonymousPage, undefined, '/api/public/scribe-ia/transcribe');
  expect([404, 405]).toContain(publicMedical.status);
  await anonymousContext.close();

  const publicPraticiens = await apiJson(page, undefined, '/api/public/praticiens');
  expect(publicPraticiens.status).toBe(200);
  expect(patientA).toBeTruthy();
});

test('Medical AI is fail-closed in the browser-facing private API', async ({ page }) => {
  test.setTimeout(120_000);
  const accessToken = await loginThroughUi(page, ADMIN_EMAIL, ADMIN_PASSWORD!);
  const patients = await apiJson(page, accessToken, '/api/private/patients');
  expect(patients.status).toBe(200);
  const patientId = patients.body?.[0]?.id;
  expect(patientId).toBeTruthy();

  const scribe = await apiJson(page, accessToken, '/api/private/scribe-ia/process', {
    method: 'POST',
    body: {
      patient_id: patientId,
      transcription_brute: 'Synthetic test consultation only; no real patient data.',
    },
  });
  expect(scribe.status).toBe(503);
  const medicalAiDetail = String(scribe.body?.detail || scribe.body || '');
  expect(medicalAiDetail).toMatch(/MEDICAL_AI_PROVIDER_APPROVED=false|LLM_ENABLED=false|services IA désactivés|Flux médical bloqué/);

  const anonymousContext = await page.context().browser().newContext({ baseURL: BASE_URL });
  const anonymousPage = await anonymousContext.newPage();
  await anonymousPage.goto('/');
  const unauthorized = await apiJson(anonymousPage, undefined, '/api/private/scribe-ia/process', {
    method: 'POST',
    body: { patient_id: patientId, transcription_brute: 'Synthetic only.' },
  });
  expect(unauthorized.status).toBe(401);
  await anonymousContext.close();
});
