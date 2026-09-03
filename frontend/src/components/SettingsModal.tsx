import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { getUserProfile, updateUserProfile, recalculateMetrics } from '../api/client';
import { X, Save, RefreshCw, UserCheck, Activity } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, onUpdated }) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      getUserProfile()
        .then((data) => setProfile(data))
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen || !profile) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateUserProfile(profile);
      onUpdated();
      onClose();
    } catch (err) {
      alert('Failed to save athlete profile');
    } finally {
      setSaving(false);
    }
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await recalculateMetrics();
      alert(
        'Fitness/fatigue chart rebuilt. Note: stored per-activity training load is ' +
        'not recomputed against new thresholds yet — new activities will use them.'
      );
      onUpdated();
    } catch (err) {
      alert('Recalculation failed');
    } finally {
      setRecalculating(false);
    }
  };

  // Convert threshold pace in sec to mm:ss for input
  const formatPaceInput = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const parsePaceInput = (str: string) => {
    const parts = str.split(':');
    if (parts.length === 2) {
      return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    }
    return 240;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Athlete Physiology Settings</h2>
              <p className="text-xs text-gray-400">Heart rate & threshold parameters used for TRIMP & PMC</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="p-5 space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Athlete Name</label>
              <input
                type="text"
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Gender (for TRIMP)</label>
              <select
                value={profile.gender}
                onChange={(e) => setProfile({ ...profile, gender: e.target.value })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Max HR (bpm)</label>
              <input
                type="number"
                value={profile.max_hr}
                onChange={(e) => setProfile({ ...profile, max_hr: parseInt(e.target.value, 10) })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Resting HR (bpm)</label>
              <input
                type="number"
                value={profile.resting_hr}
                onChange={(e) => setProfile({ ...profile, resting_hr: parseInt(e.target.value, 10) })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Lactate LTHR (bpm)</label>
              <input
                type="number"
                value={profile.lthr}
                onChange={(e) => setProfile({ ...profile, lthr: parseInt(e.target.value, 10) })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Threshold Pace (min/km)</label>
              <input
                type="text"
                defaultValue={formatPaceInput(profile.threshold_pace_sec)}
                onBlur={(e) => setProfile({ ...profile, threshold_pace_sec: parsePaceInput(e.target.value) })}
                placeholder="4:00"
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white font-mono focus:outline-none focus:border-cyan-500"
              />
              <span className="text-[10px] text-gray-500 mt-0.5 block">1-hour sustainable race pace</span>
            </div>
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Body Weight (kg)</label>
              <input
                type="number"
                step="0.5"
                value={profile.weight_kg}
                onChange={(e) => setProfile({ ...profile, weight_kg: parseFloat(e.target.value) })}
                className="w-full bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {/* Recalculate Historical button */}
          <div className="p-3 bg-gray-950/60 rounded-xl border border-gray-800 flex items-center justify-between">
            <div>
              <span className="font-bold text-gray-300 block">Recalculate Past Metrics</span>
              <span className="text-[10px] text-gray-500">Updates all previous runs with new zones & TRIMP</span>
            </div>
            <button
              type="button"
              disabled={recalculating}
              onClick={handleRecalculate}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-cyan-400 border border-gray-700 font-semibold text-[11px] transition"
            >
              <RefreshCw className={`w-3 h-3 ${recalculating ? 'animate-spin' : ''}`} />
              <span>{recalculating ? 'Processing...' : 'Recalculate'}</span>
            </button>
          </div>

          {/* Action Buttons */}
          <div className="pt-3 border-t border-gray-800 flex items-center justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 font-semibold text-xs transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 transition"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save Profile'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
