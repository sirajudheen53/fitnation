/**
 * Auth helpers — token storage and session management.
 * Uses localStorage for web. SSR-safe checks.
 */

const TOKEN_KEY = "fbos_auth_token";
const USER_KEY = "fbos_user";
const IMPERSONATION_KEY = "fbos_impersonation";

export interface StoredUser {
  id: number;
  email: string;
  name: string;
  role: string;
  tenant_id: number | null;
  tenant_name: string | null;
  is_owner: boolean;
}

/**
 * An active support-impersonation session (issue #45).
 *
 * While one is active, `getToken()`/`getStoredUser()` resolve to the
 * impersonated owner so every page and API call behaves exactly as the
 * owner's own browser would. The admin's real session is kept in the
 * stash and restored on exit (or expiry).
 */
export interface ImpersonationSession {
  token: string;
  /** ISO timestamp — the backend enforces the real (30 min) lifetime. */
  expires_at: string;
  owner_email: string;
  tenant_id: number;
  tenant_name: string;
  /** The admin's own session, restored on exit. */
  admin_token: string;
  admin_user: StoredUser;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const impersonation = activeImpersonation();
  if (impersonation) return impersonation.token;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function setStoredUser(user: StoredUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_KEY);
}

export function logout(): void {
  clearToken();
  clearStoredUser();
  // An explicit sign-out also discards any impersonation session —
  // including the stashed admin session — for a clean slate.
  clearImpersonationStash();
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

/* ── Support impersonation (issue #45) ─────────────────────────── */

function readImpersonationStash(): ImpersonationSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(IMPERSONATION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ImpersonationSession;
  } catch {
    return null;
  }
}

function clearImpersonationStash(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(IMPERSONATION_KEY);
}

/**
 * The impersonation session recorded in the stash — including one whose
 * token lifetime is already over. Pure read; see `getToken` for how an
 * expired session collapses back to the admin session.
 */
export function getImpersonationSession(): ImpersonationSession | null {
  return readImpersonationStash();
}

/**
 * Swap the browser session to the impersonated owner. The admin's own
 * token/user ride along inside the stash and come back on exit.
 */
export function startImpersonationSession(session: ImpersonationSession): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(IMPERSONATION_KEY, JSON.stringify(session));
  setToken(session.token);
  setStoredUser({
    id: 0,
    email: session.owner_email,
    name: session.owner_email,
    role: "gym_owner",
    tenant_id: session.tenant_id,
    tenant_name: session.tenant_name,
    is_owner: true,
  });
}

/**
 * Leave the impersonated session and restore the admin's own.
 * Returns the session that was ended (null if none was running).
 */
export function endImpersonationSession(): ImpersonationSession | null {
  const session = readImpersonationStash();
  clearImpersonationStash();
  if (session) {
    setToken(session.admin_token);
    setStoredUser(session.admin_user);
  }
  return session;
}

/**
 * The impersonation session whose token is still alive, if any. An expired
 * session is ended as a side effect: the token is already dead server-side,
 * so the admin's own session is restored from the stash immediately.
 */
function activeImpersonation(): ImpersonationSession | null {
  const session = readImpersonationStash();
  if (!session) return null;
  if (new Date(session.expires_at).getTime() > Date.now()) return session;
  endImpersonationSession();
  return null;
}
