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
}

export interface UserProfile {
  id: number;
  name: string;
  gender: string;
  max_hr: number;
  resting_hr: number;
  lthr: number;
  threshold_pace_sec: number;
  weight_kg: number;
  hr_zones?: Record<string, [number, number]>;
  pace_zones?: Record<string, [number, number]>;
}
