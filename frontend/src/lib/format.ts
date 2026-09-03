import { Activity } from '../types';

export const RUNNING_SPORTS = ['running', 'treadmill'];
export const isRunning = (s?: string) => RUNNING_SPORTS.includes((s || '').toLowerCase());

/** Pace is only meaningful where distance was actually measured. */
export const pace = (secPerKm?: number | null): string => {
  if (!secPerKm || !isFinite(secPerKm) || secPerKm <= 0) return '—';
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

export const duration = (sec?: number | null): string => {
  if (!sec || sec <= 0) return '—';
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
};

export const km = (meters?: number | null, digits = 2): string =>
  !meters || meters <= 0 ? '—' : (meters / 1000).toFixed(digits);

export const dateLabel = (iso: string): string =>
  new Date(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });

export const timeLabel = (iso: string): string =>
  new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

export type SportKey = 'runs' | 'walks' | 'gym';

export const SPORTS: Record<SportKey, {
  label: string;
  match: (s: string) => boolean;
  color: string;
  /** Sports without a measured distance are described by time and effort. */
  hasPace: boolean;
}> = {
  runs:  { label: 'Runs',  match: isRunning,                      color: 'var(--run)',  hasPace: true },
  walks: { label: 'Walks', match: (s) => ['walking', 'hiking'].includes(s), color: 'var(--walk)', hasPace: true },
  gym:   { label: 'Gym',   match: (s) => !isRunning(s) && !['walking', 'hiking'].includes(s), color: 'var(--gym)', hasPace: false },
};

export const bucketOf = (a: Activity): SportKey => {
  const s = (a.sport_type || '').toLowerCase();
  if (SPORTS.runs.match(s)) return 'runs';
  if (SPORTS.walks.match(s)) return 'walks';
  return 'gym';
};

/**
 * Why a figure is missing, straight from the server. Showing the reason is the
 * point: a dash with an explanation is trustworthy, a zero is not.
 */
export const whyMissing = (a: Activity, key: string): string | undefined =>
  a.data_quality?.unavailable?.[key];
