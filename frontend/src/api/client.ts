import axios from 'axios';
import { Activity, PMCPoint, DashboardSummary, UserProfile, BestEffort, HomeData } from '../types';

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
  headers: {
    'Content-Type': 'application/json',
  },
});

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
