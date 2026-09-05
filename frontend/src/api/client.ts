import axios from 'axios';
import {
  Activity, PMCPoint, DashboardSummary, UserProfile, BestEffort, HomeData,
  AdminAccount, AdminOverview, BackupFile, PeriodReport, ReportPeriodOption,
  TrainingCalendar, CycleSummary, CycleCalendarMonth, ThresholdSuggestion,
} from '../types';
import { loadSession, saveSession } from '../lib/auth';

/**
 * Served by nginx the API is same-origin, so a relative base is right. Loaded
 * from local assets inside the Android app there is no origin to be relative
 * to, so the host passes an absolute base in the URL fragment.
 */
const apiBaseFromHash = (): string | null => {
  const m = /(?:^|[#&])api=([^&]+)/.exec(window.location.hash);
  return m ? decodeURIComponent(m[1]).replace(/\/$/, '') : null;
};

const API_BASE = apiBaseFromHash() ?? '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Every request carries the session, and a rejected session clears itself so
// the app falls back to the sign-in screen rather than silently failing.
api.interceptors.request.use((config) => {
  const session = loadSession();
  if (session?.token) config.headers.Authorization = `Bearer ${session.token}`;
  return config;
});

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      saveSession(null);
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

export interface AuthStatus {
  has_accounts: boolean;
  accounts: number;
  unclaimed_activities: number;
}

export const getAuthStatus = async (): Promise<AuthStatus> =>
  (await api.get<AuthStatus>('/auth/status')).data;

export const register = async (
  username: string, password: string, display_name?: string, data_source = 'health_connect'
) => {
  const res = await api.post('/auth/register', { username, password, display_name, data_source });
  saveSession(res.data);
  return res.data;
};

export const login = async (username: string, password: string) => {
  const res = await api.post('/auth/login', { username, password });
  saveSession(res.data);
  return res.data;
};

/**
 * Download this athlete's own data.
 *
 * Separate from the server backup, which covers every account at once and
 * exists to restore the system rather than to hand anyone their history.
 */
export const exportMyData = async (includeStreams: boolean): Promise<void> => {
  const res = await api.get('/auth/export', {
    params: { include_streams: includeStreams },
    responseType: 'blob',
  });
  const url = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `performance-export-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
};

export const deleteAccount = async (password: string): Promise<void> => {
  // Sent in the body of a DELETE, which axios needs told about explicitly.
  await api.delete('/auth/me', { data: { password, confirm: 'DELETE' } });
  saveSession(null);
};

export interface Me {
  user_id: string; username: string; display_name?: string | null;
  is_admin: boolean; data_source: string; cycle_tracking?: boolean;
}

/**
 * Re-read who we are and fold it back into the stored session.
 *
 * A session saved before a field existed will never gain it otherwise, so a
 * long-lived login would keep hiding features it should now see.
 */
export const refreshMe = async (): Promise<Me> => {
  const me = (await api.get<Me>('/auth/me')).data;
  const session = loadSession();
  if (session) saveSession({ ...session, user_id: me.user_id, is_admin: me.is_admin,
                             data_source: me.data_source });
  return me;
};

export const adminOverview = async (): Promise<AdminOverview> =>
  (await api.get<AdminOverview>('/admin/overview')).data;

export const adminUsers = async (): Promise<AdminAccount[]> =>
  (await api.get<AdminAccount[]>('/admin/users')).data;

export const adminUpdateUser = async (
  id: string, patch: { is_active?: boolean; is_admin?: boolean }
): Promise<AdminAccount> => (await api.patch<AdminAccount>(`/admin/users/${id}`, patch)).data;

export const adminDeleteUser = async (id: string): Promise<void> => {
  await api.delete(`/admin/users/${id}`);
};

export const adminBackups = async (): Promise<{
  backups: BackupFile[]; count: number; total_mb: number; retention_days: number;
  keep_minimum: number; compressed: boolean; directory: string;
}> => (await api.get('/admin/backups')).data;

export const adminCreateBackup = async () => (await api.post('/admin/backups')).data;
export const adminPruneBackups = async () => (await api.delete('/admin/backups')).data;

export const setDataSource = async (data_source: string): Promise<Me> => {
  const me = (await api.patch<Me>('/auth/me/source', { data_source })).data;
  const session = loadSession();
  if (session) saveSession({ ...session, data_source: me.data_source });
  return me;
};

/** Import exported activity files: GPX, TCX, FIT, or a zip of them. */
export const importFiles = async (files: File[]): Promise<{
  imported: number; skipped: number; problems: string[]; problem_count: number;
}> => {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await api.post('/sync/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,   // a bulk archive can hold hundreds of activities
  });
  return res.data;
};

export interface DeviceConnection {
  provider: string; account_label?: string | null; enabled: boolean;
  last_synced_at?: string | null; last_status?: string | null; last_ok: boolean;
}

export const getConnection = async (): Promise<DeviceConnection | null> =>
  (await api.get<DeviceConnection | null>('/connections')).data;

export const connectGarmin = async (email: string, password: string, mfa_code?: string) =>
  (await api.post<DeviceConnection>('/connections/garmin', { email, password, mfa_code })).data;

export const disconnectDevice = async () => { await api.delete('/connections'); };

export const syncConnection = async (): Promise<{
  imported: number; skipped: number; found: number; message: string;
}> => (await api.post('/connections/sync', null, { timeout: 300000 })).data;

export interface CoachNote {
  available: boolean; text?: string | null; model?: string | null;
  created_at?: string | null; generated?: boolean; reason?: string | null;
}

export const getActivityNote = async (id: string, refresh = false): Promise<CoachNote> =>
  (await api.get<CoachNote>(`/coach/activity/${id}`, {
    params: { refresh }, timeout: 180000,   // a local model takes seconds, not milliseconds
  })).data;

export const getWeeklyNote = async (refresh = false): Promise<CoachNote> =>
  (await api.get<CoachNote>('/coach/week', { params: { refresh }, timeout: 180000 })).data;

export const getPeriodNote = async (
  kind: string, key?: string, offset = 0, refresh = false
): Promise<CoachNote> =>
  (await api.get<CoachNote>('/coach/period', {
    params: { kind, key, offset, refresh }, timeout: 180000,
  })).data;

export const getCoachStatus = async (): Promise<{
  enabled: boolean; reachable?: boolean; url?: string; model?: string;
  available_models?: string[]; reason?: string;
}> => (await api.get('/coach/status')).data;

export const logout = async () => {
  try { await api.post('/auth/logout'); } finally { saveSession(null); }
};

export const getActivities = async (): Promise<Activity[]> => {
  // The dashboard groups by sport client-side, so it needs the whole history
  // rather than the first page.
  const res = await api.get<Activity[]>('/activities', { params: { limit: 500 } });
  return res.data;
};

export const getActivityDetail = async (id: string): Promise<Activity> => {
  const res = await api.get<Activity>(`/activities/${id}`);
  return res.data;
};

export const deleteActivity = async (id: string): Promise<void> => {
  await api.delete(`/activities/${id}`);
};

export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const res = await api.get<DashboardSummary>('/metrics/summary');
  return res.data;
};

export const getPMCData = async (days = 90): Promise<PMCPoint[]> => {
  const res = await api.get<PMCPoint[]>(`/metrics/pmc?days=${days}`);
  return res.data;
};

export const getHome = async (): Promise<HomeData> => {
  const res = await api.get<HomeData>('/metrics/home');
  return res.data;
};

export const getPersonalRecords = async (): Promise<BestEffort[]> => {
  const res = await api.get<BestEffort[]>('/metrics/records');
  return res.data;
};

export const getUserProfile = async (): Promise<UserProfile> => {
  const res = await api.get<UserProfile>('/settings/profile');
  return res.data;
};

export const updateUserProfile = async (profile: UserProfile): Promise<UserProfile> => {
  const res = await api.put<UserProfile>('/settings/profile', profile);
  return res.data;
};

export const recalculateMetrics = async (): Promise<void> => {
  await api.post('/settings/recalculate');
};

export const uploadGPX = async (file: File): Promise<Activity> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post<Activity>('/sync/upload-gpx', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return res.data;
};

// ------------------------------------------------------------- reports ---

export const getWeekReport = async (offset = 0, key?: string): Promise<PeriodReport> =>
  (await api.get<PeriodReport>('/reports/week', { params: { offset, key } })).data;

export const getPeriodReport = async (
  kind: 'week' | 'month' | 'year', key?: string, offset = 0
): Promise<PeriodReport> =>
  (await api.get<PeriodReport>('/reports/period', { params: { kind, key, offset } })).data;

export const getReportPeriods = async (
  kind: 'month' | 'year'
): Promise<ReportPeriodOption[]> =>
  (await api.get<ReportPeriodOption[]>('/reports/periods', { params: { kind } })).data;

/**
 * Fetch a report as a PDF and hand it to the browser.
 *
 * Downloaded through the API client rather than by pointing the browser at the
 * URL, because the session lives in a header: a plain link would arrive
 * unauthenticated. Generating one can take a while when the coach's note is
 * being written, hence the long timeout.
 */
export const downloadReportPdf = async (
  kind: 'week' | 'month' | 'year', key: string, includeNote = true
): Promise<void> => {
  const res = await api.get('/reports/pdf', {
    params: { kind, key, include_note: includeNote },
    responseType: 'blob',
    timeout: 240000,
  });
  const blob = new Blob([res.data], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `performance-${key}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked on a delay: the Android WebView reads the blob asynchronously
  // through its download bridge, and revoking immediately races it.
  setTimeout(() => URL.revokeObjectURL(url), 30000);
};

export const getTrainingCalendar = async (month?: string): Promise<TrainingCalendar> =>
  (await api.get<TrainingCalendar>('/reports/calendar', { params: { month } })).data;

// --------------------------------------------------------------- cycle ---
// Off by default and per account. Nothing here is sent anywhere but this
// server, and the coach is deliberately never given it.

export const getCycleSummary = async (): Promise<CycleSummary> =>
  (await api.get<CycleSummary>('/cycle')).data;

export const setCycleTracking = async (enabled: boolean): Promise<{ enabled: boolean }> =>
  (await api.put('/cycle/enabled', { enabled })).data;

export const getCycleCalendar = async (month?: string): Promise<CycleCalendarMonth> =>
  (await api.get<CycleCalendarMonth>('/cycle/calendar', { params: { month } })).data;

export const logCycleDay = async (date: string, flow?: string | null) =>
  (await api.put('/cycle/day', { date, flow: flow ?? null })).data;

export const unlogCycleDay = async (date: string) =>
  (await api.delete('/cycle/day', { params: { date } })).data;

// -------------------------------------------------------------- avatar ---

export const uploadAvatar = async (image: Blob): Promise<void> => {
  const form = new FormData();
  form.append('file', image, 'avatar.jpg');
  // The content type is left to the browser: it has to set the multipart
  // boundary, and the client default would override it with the wrong value.
  await api.post('/settings/avatar', form, { headers: { 'Content-Type': undefined } });
};

export const deleteAvatar = async (): Promise<void> => {
  await api.delete('/settings/avatar');
};

/**
 * The athlete's picture as an object URL, or null if there is none.
 *
 * Fetched rather than pointed at with an img src, because the endpoint is
 * behind the session and an img tag cannot carry the header. The caller owns
 * the returned URL and must revoke it.
 */
export const fetchAvatarUrl = async (): Promise<string | null> => {
  try {
    const res = await api.get('/settings/avatar', { responseType: 'blob' });
    return URL.createObjectURL(res.data as Blob);
  } catch {
    return null;
  }
};

/** Correct or annotate one activity. Only the fields sent are changed. */
export const editActivity = async (
  id: string,
  changes: Partial<Pick<Activity,
    'name' | 'sport_type' | 'workout_tag' | 'notes' | 'calories_kcal' | 'steps'>>
): Promise<Activity> => (await api.patch<Activity>(`/activities/${id}`, changes)).data;

export const getWorkoutTags = async (): Promise<string[]> =>
  (await api.get<{ tags: string[] }>('/activities/tags')).data.tags;

export const getThresholdSuggestion = async (): Promise<ThresholdSuggestion> =>
  (await api.get<ThresholdSuggestion>('/settings/threshold-suggestion')).data;
