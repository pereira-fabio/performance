import axios from 'axios';
import { Activity, PMCPoint, DashboardSummary, UserProfile, BestEffort, HomeData } from '../types';
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

export const register = async (username: string, password: string, display_name?: string) => {
  const res = await api.post('/auth/register', { username, password, display_name });
  saveSession(res.data);
  return res.data;
};

export const login = async (username: string, password: string) => {
  const res = await api.post('/auth/login', { username, password });
  saveSession(res.data);
  return res.data;
};

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
