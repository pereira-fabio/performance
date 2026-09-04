export interface Split {
  split_number: number;
  distance_meters: number;
  elapsed_time_sec: number;
  pace_sec_km: number;
  gap_sec_km?: number;
  avg_hr?: number;
  avg_cadence?: number;
  elevation_diff_m?: number;
  aerobic_efficiency?: number;
  is_partial?: boolean;
}

export interface BestEffort {
  label: string;
  distance_meters: number;
  time_seconds: number;
  pace_sec_km: number;
  is_personal_record: boolean;
}

export interface StreamPoint {
  time: string;
  timestamp_offset: number;
  lat?: number;
  lng?: number;
  altitude?: number;
  distance: number;
  speed: number;
  grade: number;
  gap_speed: number;
  heart_rate?: number;
  cadence?: number;
}

export interface Activity {
  id: string;
  external_id?: string;
  name: string;
  sport_type: string;
  start_time: string;
  end_time: string;
  elapsed_time_sec: number;
  moving_time_sec: number;
  distance_meters: number;
  avg_pace_sec_km?: number;
  gap_pace_sec_km?: number;
  avg_hr?: number;
  max_hr?: number;
  min_hr?: number;
  avg_cadence?: number;
  max_cadence?: number;
  avg_stride_length_m?: number;
  elevation_gain_m?: number;
  elevation_loss_m?: number;
  aerobic_decoupling_pct?: number;
  aerobic_efficiency_factor?: number;
  trimp_banister?: number;
  trimp_edwards?: number;
  r_tss?: number;
  intensity_factor?: number;
  training_effect_aerobic?: number;
  training_effect_anaerobic?: number;
  recovery_hours?: number;
  xp?: number;
  steps?: number;
  vo2_max?: number;
  max_speed_mps?: number;
  hr_zone_seconds?: Record<string, number>;
  pace_zone_seconds?: Record<string, number>;
  calories_kcal?: number;
  hr_coverage?: number;
  // Per-channel coverage plus an `unavailable` map keyed by metric name,
  // explaining any figure the device data could not support.
  data_quality?: {
    unavailable?: Record<string, string>;
    rtss_basis?: string;
    [key: string]: unknown;
  };
  source: string;
  notes?: string;
  created_at: string;
  splits?: Split[];
  best_efforts?: BestEffort[];
  stream_data?: {
    points: StreamPoint[];
  };
}

export interface PMCPoint {
  date: string;
  daily_tss: number;
  ctl: number;
  atl: number;
  tsb: number;
  resting_hr?: number;
  hrv_rmssd?: number;
  readiness_score?: number;
}

export interface DashboardSummary {
  volume_7d_km: number;
  tss_7d: number;
  time_7d_sec: number;
  runs_7d_count: number;
  volume_28d_km: number;
  tss_28d: number;
  ctl: number;
  atl: number;
  tsb: number;
  acwr: number;
  readiness_score?: number;
  avg_decoupling_28d?: number;
  // Non-running activity in the last 7 days, keyed by sport. Kept out of the
  // running volume and training-load figures above.
  other_sports_7d?: Record<string, { count: number; km: number; tss: number }>;
  /** Volume, time and load per sport over 7 and 28 days. */
  by_sport?: Record<string, {
    count_7d: number; km_7d: number; time_7d_sec: number; load_7d: number;
    count_28d: number; km_28d: number; time_28d_sec: number; load_28d: number;
  }>;
}

export interface Achievement {
  key: string;
  name: string;
  detail: string;
  earned: boolean;
  progress: number;
  value?: string;
}

export interface HomeData {
  empty: boolean;
  progression: {
    level: number; xp: number; xp_into_level: number; xp_for_next: number; progress_pct: number;
  };
  attributes: Record<string, number>;
  split: Record<string, { count: number; hours: number; km: number; xp: number }>;
  streak_weeks: number;
  totals: { activities: number; runs: number; km: number; hours: number };
  form: { ctl: number; tsb: number; readiness?: number | null };
  vo2_max?: number | null;
  resting_hr?: number | null;
  achievements: Achievement[];
}

export interface AdminAccount {
  id: string;
  username: string;
  display_name?: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  activities: number;
  last_activity?: string | null;
  sessions: number;
}

export interface BackupFile {
  name: string; size_mb: number; created: string; age_days: number; compressed: boolean;
}

export interface AdminOverview {
  accounts: number; active_accounts: number; activities: number;
  unowned_activities: number; database_mb?: number | null;
  backups: number; backup_total_mb: number; newest_backup?: BackupFile | null;
}

export interface UserProfile {
  id?: string | null;
  name: string;
  gender: string;
  max_hr: number;
  resting_hr: number;
  lthr: number;
  threshold_pace_sec: number;
  weight_kg: number;
  height_cm?: number | null;
  /** ISO date. Stored rather than an age, so it does not go stale. */
  birth_date?: string | null;
  hr_zones?: Record<string, [number, number]>;
  pace_zones?: Record<string, [number, number]>;
}

/** A change in a figure against the same figure in the previous period. */
export interface Delta {
  change: number | null;
  pct: number | null;
}

export interface PeriodTotals {
  sessions: number;
  runs: number;
  km: number | null;
  moving_sec: number;
  elapsed_sec: number;
  load: number | null;
  elevation_gain_m: number | null;
  calories: number | null;
  xp: number;
  steps?: number | null;
  avg_pace_sec_km: number | null;
  avg_gap_sec_km: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_cadence: number | null;
  avg_stride_m: number | null;
  avg_decoupling_pct: number | null;
  avg_training_effect: number | null;
  longest_km: number | null;
  fastest_pace_sec_km: number | null;
  fastest_name: string | null;
  days_trained: number;
  hr_zone_seconds: Record<string, number> | null;
}

export interface PeriodBucket {
  date: string;
  label: string;
  km: number | null;
  load: number | null;
  moving_sec: number;
  sessions: number;
}

export interface ReportSession {
  id: string;
  name: string;
  sport_type: string;
  start_time: string;
  km: number | null;
  moving_sec: number;
  pace_sec_km: number | null;
  gap_sec_km: number | null;
  avg_hr: number | null;
  load: number | null;
  elevation_gain_m: number | null;
  training_effect: number | null;
  decoupling_pct: number | null;
  is_run: boolean;
}

export interface PeriodReport {
  kind: 'week' | 'month' | 'year';
  key: string;
  label: string;
  start: string;
  end: string;
  complete: boolean;
  day_count: number;
  empty: boolean;
  totals: PeriodTotals;
  previous: { key: string; label: string; totals: PeriodTotals };
  deltas: Record<string, Delta | null>;
  breakdown: { unit: 'day' | 'month'; rows: PeriodBucket[] };
  sessions: ReportSession[];
  other_sports: Record<string, { count: number; km: number; moving_sec: number; load: number }>;
  records: {
    label: string;
    time_seconds: number;
    pace_sec_km: number;
    achieved_at: string;
    is_personal_record: boolean;
  }[];
  form: {
    ctl_start: number | null;
    ctl_end: number | null;
    atl_end: number | null;
    tsb_end: number | null;
    acwr_end: number | null;
  };
  offset?: number;
  previous_key?: string | null;
  next_key?: string | null;
}

export interface ReportPeriodOption {
  key: string;
  label: string;
  complete: boolean;
}

/** A month of training days, for picking a week off a calendar. */
export interface TrainingCalendar {
  month: string;
  days: Record<string, { sessions: number; km: number; sports: string[] }>;
  earliest: string | null;
  today: string;
}

export type CyclePhase = 'period' | 'follicular' | 'ovulation' | 'luteal' | null;

export interface CycleSummary {
  enabled: boolean;
  logged_days: number;
  periods_recorded: number;
  has_prediction: boolean;
  last_period_start: string | null;
  last_period_days: number | null;
  average_cycle_days: number | null;
  average_period_days: number | null;
  cycle_range: [number, number] | null;
  cycle_day: number | null;
  phase: CyclePhase;
  predicted_next_start: string | null;
  predicted_window: [string, string] | null;
  days_until_next: number | null;
  confidence: 'none' | 'low' | 'moderate' | 'high';
  reason: string | null;
}

export interface CycleCalendarMonth {
  month: string;
  days: Record<string, { flow: string | null; notes: string | null }>;
  predicted: string[];
  today: string;
}
