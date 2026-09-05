import React, { useState, useEffect, useRef } from 'react';
import { UserProfile } from '../types';
import {
  getUserProfile, updateUserProfile, uploadAvatar, deleteAvatar,
  getThresholdSuggestion,
} from '../api/client';
import { ThresholdSuggestion } from '../types';
import { Modal, Field, input, button } from './Modal';
import { describeError } from '../lib/errors';
import { squareThumbnail } from '../lib/image';
import { Avatar } from './Avatar';

/**
 * The athlete's own numbers.
 *
 * Split into what is measured about the body and what is measured about
 * training, because they are answered from different places: height and weight
 * off a scale, thresholds off a test or a hard effort.
 *
 * Each field says what it actually affects. Several of them feed real
 * calculations and one or two are only recorded, and quietly mixing the two
 * would imply the app is doing more with them than it is.
 */

const GENDERS = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'unspecified', label: 'Prefer not to say' },
];

const ageFrom = (iso?: string | null): number | null => {
  if (!iso) return null;
  const born = new Date(iso);
  if (isNaN(born.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - born.getFullYear();
  const monthDiff = now.getMonth() - born.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < born.getDate())) age -= 1;
  return age >= 0 && age < 130 ? age : null;
};

/**
 * Nes et al. (2013), which tracks measured maxima better than 220 - age across
 * a wide age range. Offered as a starting point, never applied on its own: a
 * measured maximum from a hard effort beats any formula, and silently
 * overwriting one with an estimate would make the zones worse.
 */
const estimatedMaxHr = (age: number): number => Math.round(211 - 0.64 * age);

export const SettingsModal: React.FC<{
  isOpen: boolean; onClose: () => void; onUpdated: () => void;
  onSignOut: () => void;
  username?: string;
}> = ({ isOpen, onClose, onUpdated, onSignOut, username }) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  // Bumped after an upload so the preview re-reads rather than showing the
  // picture that was there a moment ago.
  const [avatarVersion, setAvatarVersion] = useState(0);
  const [picture, setPicture] = useState(false);
  const [threshold, setThreshold] = useState<ThresholdSuggestion | null>(null);
  // The pace box is uncontrolled so it can be typed in freely, so changing it
  // from a button needs a key change to make React rebuild it.
  const [paceKey, setPaceKey] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setNote(null);
    getUserProfile()
      .then((p) => { setProfile(p); setPicture(!!p.has_avatar); })
      .catch((e) => setNote(describeError(e, 'Could not load your profile')));
    // Worked out from the athlete's own running, and only ever offered.
    getThresholdSuggestion().then(setThreshold).catch(() => setThreshold(null));
  }, [isOpen]);

  if (!isOpen) return null;

  const set = <K extends keyof UserProfile>(key: K, value: UserProfile[K]) =>
    setProfile((p) => (p ? { ...p, [key]: value } : p));

  const paceText = (sec: number) =>
    `${Math.floor(sec / 60)}:${Math.round(sec % 60).toString().padStart(2, '0')}`;
  const paceSec = (t: string) => {
    const [m, s] = t.split(':').map(Number);
    return isFinite(m) && isFinite(s) ? m * 60 + s : profile?.threshold_pace_sec ?? 240;
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setNote(null);
    try {
      await updateUserProfile(profile);
      onUpdated();
      onClose();
    } catch (err) {
      setNote(describeError(err, 'Could not save your profile'));
    } finally {
      setSaving(false);
    }
  };

  const age = ageFrom(profile?.birth_date);
  const suggestion = age != null ? estimatedMaxHr(age) : null;
  const needsHips = (profile?.gender ?? '').toLowerCase() === 'female';
  const comp = profile?.composition;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Profile"
           subtitle="Your numbers, and what they are used for">
      {!profile ? (
        <p className="text-[13px] text-muted">{note ?? 'Loading…'}</p>
      ) : (
        <form onSubmit={save} className="space-y-5">
          <div className="flex items-center gap-4">
            <div className="shrink-0 h-16 w-16 rounded-2xl overflow-hidden grid place-items-center
                            bg-surface border border-line text-faint">
              <Avatar size={64} version={avatarVersion}
                      fallback={<span className="text-2xs">No picture</span>} />
            </div>
            <div className="min-w-0">
              <input ref={fileInput} type="file" accept="image/*" className="hidden"
                     onChange={async (e) => {
                       const file = e.target.files?.[0];
                       // Cleared straight away so choosing the same file twice
                       // still fires a change event.
                       e.target.value = '';
                       if (!file) return;
                       setSaving(true);
                       setNote(null);
                       try {
                         await uploadAvatar(await squareThumbnail(file));
                         setAvatarVersion((v) => v + 1);
                         setPicture(true);
                         onUpdated();
                       } catch (err: any) {
                         setNote(err?.message ?? describeError(err, 'Could not save that picture'));
                       } finally {
                         setSaving(false);
                       }
                     }} />
              <button type="button" disabled={saving} onClick={() => fileInput.current?.click()}
                      className="text-xs font-semibold text-accent hover:underline disabled:opacity-50">
                {picture ? 'Change picture' : 'Upload a picture'}
              </button>
              {picture && (
                <button type="button" disabled={saving}
                        onClick={async () => {
                          setSaving(true);
                          try {
                            await deleteAvatar();
                            setAvatarVersion((v) => v + 1);
                            setPicture(false);
                            onUpdated();
                          } finally {
                            setSaving(false);
                          }
                        }}
                        className="ml-3 text-xs text-faint hover:text-negative transition">
                  Remove
                </button>
              )}
              <p className="mt-1 text-2xs text-faint">
                Shown on your home page in place of the level number. Cropped to a square and
                scaled down here before it is sent.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <Field label="Name">
              <input className={input} value={profile.name}
                     onChange={(e) => set('name', e.target.value)} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Date of birth"
                     hint={age != null ? `${age} years old` : 'used to suggest your max heart rate'}>
                <input type="date" className={input} value={profile.birth_date ?? ''}
                       max={new Date().toISOString().slice(0, 10)}
                       onChange={(e) => set('birth_date', e.target.value || null)} />
              </Field>
              <Field label="Sex" hint="changes the training-load formula">
                <select className={input} value={profile.gender || 'unspecified'}
                        onChange={(e) => set('gender', e.target.value)}>
                  {GENDERS.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Height" hint="cm">
                <input type="number" step="0.5" min="80" max="250" className={input}
                       value={profile.height_cm ?? ''} placeholder="—"
                       onChange={(e) =>
                         set('height_cm', e.target.value === '' ? null : +e.target.value)} />
              </Field>
              <Field label="Weight" hint="kg">
                <input type="number" step="0.1" min="25" max="300" className={input}
                       value={profile.weight_kg}
                       onChange={(e) => set('weight_kg', +e.target.value)} />
              </Field>
            </div>
          </div>

          <div className="pt-4 border-t border-line space-y-3">
            <div className="text-xs text-muted">Measurements</div>

            <div className={`grid gap-3 ${needsHips ? 'grid-cols-3' : 'grid-cols-2'}`}>
              <Field label="Neck" hint="cm">
                <input type="number" step="0.5" min="20" max="70" className={input}
                       value={profile.neck_cm ?? ''} placeholder="—"
                       onChange={(e) =>
                         set('neck_cm', e.target.value === '' ? null : +e.target.value)} />
              </Field>
              <Field label="Waist" hint="cm">
                <input type="number" step="0.5" min="40" max="200" className={input}
                       value={profile.waist_cm ?? ''} placeholder="—"
                       onChange={(e) =>
                         set('waist_cm', e.target.value === '' ? null : +e.target.value)} />
              </Field>
              {/* Only the female formula uses hips, so the field only appears
                  where it would be used rather than sitting there ignored. */}
              {needsHips && (
                <Field label="Hips" hint="cm">
                  <input type="number" step="0.5" min="50" max="200" className={input}
                         value={profile.hip_cm ?? ''} placeholder="—"
                         onChange={(e) =>
                           set('hip_cm', e.target.value === '' ? null : +e.target.value)} />
                </Field>
              )}
            </div>

            {comp && (comp.bmi != null || comp.body_fat_percent != null) ? (
              <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-surface border border-line">
                <div>
                  <div className="text-2xs text-faint">BMI</div>
                  <div className="text-base font-semibold tnum text-fg-strong">
                    {comp.bmi ?? '—'}
                  </div>
                </div>
                <div>
                  <div className="text-2xs text-faint">Body fat</div>
                  <div className="text-base font-semibold tnum text-fg-strong">
                    {comp.body_fat_percent != null ? `${comp.body_fat_percent}%` : '—'}
                  </div>
                  {comp.body_fat_band && (
                    <div className="text-2xs text-muted">{comp.body_fat_band}</div>
                  )}
                </div>
                <div>
                  <div className="text-2xs text-faint">Lean mass</div>
                  <div className="text-base font-semibold tnum text-fg-strong">
                    {comp.lean_mass_kg != null ? `${comp.lean_mass_kg} kg` : '—'}
                  </div>
                </div>
              </div>
            ) : null}

            <p className="text-2xs text-faint">
              Body fat is estimated from your girths by the US Navy method, which is
              repeatable with a tape measure and useful for watching a direction rather
              than an absolute. BMI is only weight over height squared and cannot tell
              muscle from fat, which is why it reads a trained runner as heavy. Both are
              estimates; neither is a diagnosis. Saved figures update when you save.
            </p>
          </div>

          <div className="pt-4 border-t border-line space-y-3">
            <div className="text-xs text-muted">Training thresholds</div>

            <div className="grid grid-cols-3 gap-3">
              <Field label="Max HR">
                <input type="number" min="100" max="230" className={input} value={profile.max_hr}
                       onChange={(e) => set('max_hr', +e.target.value)} />
              </Field>
              <Field label="Resting HR">
                <input type="number" min="25" max="120" className={input} value={profile.resting_hr}
                       onChange={(e) => set('resting_hr', +e.target.value)} />
              </Field>
              <Field label="Threshold HR">
                <input type="number" min="90" max="220" className={input} value={profile.lthr}
                       onChange={(e) => set('lthr', +e.target.value)} />
              </Field>
            </div>

            {suggestion != null && suggestion !== profile.max_hr && (
              <button type="button" onClick={() => set('max_hr', suggestion)}
                      className="text-2xs text-accent hover:underline">
                Estimate {suggestion} bpm from your age
              </button>
            )}

            <Field label="Threshold pace" hint="min:sec per km — the pace you could hold for an hour">
              <input key={paceKey} className={input}
                     defaultValue={paceText(profile.threshold_pace_sec)}
                     onBlur={(e) => set('threshold_pace_sec', paceSec(e.target.value))} />
            </Field>

            {/* Offered, never applied. An athlete who has measured this in a
                test knows better than either estimate, and overwriting that
                would make every zone worse. */}
            {threshold?.pace_sec_km != null
              && Math.abs(threshold.pace_sec_km - profile.threshold_pace_sec) > 2 && (
              <button type="button"
                      onClick={() => {
                        set('threshold_pace_sec', threshold.pace_sec_km!);
                        setPaceKey((k) => k + 1);
                      }}
                      className="text-2xs text-accent hover:underline text-left">
                Use {paceText(threshold.pace_sec_km)} /km, from {threshold.detail}
              </button>
            )}

            <p className="text-2xs text-faint">
              Heart-rate zones and training load come from these. Left at the defaults every
              run lands in the same zone and every load figure is wrong, so they are worth
              setting before anything else. Changing them affects new activities and the
              fitness curve; the load already stored on past activities is not recalculated.
            </p>
          </div>

          {note && <p className="text-2xs text-negative">{note}</p>}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
                    className={`${button} text-muted hover:text-fg`}>Cancel</button>
            <button type="submit" disabled={saving}
                    className={`${button} bg-accent text-white hover:opacity-90`}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>

          {/* Set apart from the buttons you actually came for. Signing out
              throws away what you were doing and there is no undo, so it gets
              its own space and its own rule rather than sharing an edge with
              Save. */}
          <div className="mt-8 pt-4 pb-1 border-t border-line
                          flex items-center justify-between gap-3">
            <span className="text-2xs text-faint truncate">
              {username ? `Signed in as ${username}` : 'Signed in'}
            </span>
            <button type="button" onClick={onSignOut}
                    className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                               border border-line text-xs font-semibold text-muted
                               hover:text-negative hover:border-negative transition">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <path d="M16 17l5-5-5-5" /><path d="M21 12H9" />
              </svg>
              Sign out
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
};
