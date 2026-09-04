const KEY = 'performance.session';

export interface StoredSession {
  token: string;
  username: string;
  display_name?: string | null;
  user_id?: string;
  is_admin?: boolean;
}

export const loadSession = (): StoredSession | null => {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
};

export const saveSession = (s: StoredSession | null): void => {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* Storage unavailable: the session simply lasts for this page load. */
  }
};
