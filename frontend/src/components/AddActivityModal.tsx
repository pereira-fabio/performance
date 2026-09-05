import React, { useEffect, useState } from 'react';
import { Modal, Field, input, button } from './Modal';
import { createActivity, getWorkoutTags } from '../api/client';
import { describeError } from '../lib/errors';

/**
 * Record an activity by hand.
 *
 * For a session that never reached the phone at all: a watch that failed to
 * export it, a run on someone else's device, a race with nothing but a result.
 *
 * It asks only for what a person can actually know. Grade-adjusted pace,
 * decoupling, fitness and fatigue are not offered, because a figure typed into
 * those boxes would be indistinguishable from one the server computed and would
 * quietly corrupt every trend built on them. Pace is not asked for either — it
 * follows from distance and duration, and asking would invite the two to
 * disagree.
 */

const SPORTS = [
  { value: 'running', label: 'Run' },
  { value: 'treadmill', label: 'Treadmill run' },
  { value: 'walking', label: 'Walk' },
  { value: 'hiking', label: 'Hike' },
  { value: 'cycling', label: 'Ride' },
  { value: 'swimming', label: 'Swim' },
  { value: 'rowing', label: 'Row' },
  { value: 'gym', label: 'Gym session' },
  { value: 'other', label: 'Other' },
];

const TAG_LABELS: Record<string, string> = {
  recovery: 'Recovery', easy: 'Easy', long: 'Long',
  tempo: 'Tempo', interval: 'Intervals', race: 'Race',
};

/** Local date and time, in the shape a datetime-local input wants. */
const nowLocal = (): string => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

const numberOrNull = (v: string): number | null => (v === '' ? null : Number(v));

export const AddActivityModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}> = ({ isOpen, onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [sport, setSport] = useState('running');
  const [when, setWhen] = useState(nowLocal());
  const [hours, setHours] = useState('');
  const [minutes, setMinutes] = useState('');
  const [seconds, setSeconds] = useState('');
  const [distanceKm, setDistanceKm] = useState('');
  const [avgHr, setAvgHr] = useState('');
  const [maxHr, setMaxHr] = useState('');
  const [ascent, setAscent] = useState('');
  const [calories, setCalories] = useState('');
  const [steps, setSteps] = useState('');
  const [tag, setTag] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setName(''); setSport('running'); setWhen(nowLocal());
    setHours(''); setMinutes(''); setSeconds('');
    setDistanceKm(''); setAvgHr(''); setMaxHr(''); setAscent('');
    setCalories(''); setSteps(''); setTag(null); setNotes('');
    setError(null);
  }, [isOpen]);

  useEffect(() => { getWorkoutTags().then(setTags).catch(() => setTags([])); }, []);

  if (!isOpen) return null;

  const durationSec =
    (Number(hours) || 0) * 3600 + (Number(minutes) || 0) * 60 + (Number(seconds) || 0);
  const km = Number(distanceKm) || 0;
  // Shown as it is typed, so the figure that will be stored is visible before
  // saving rather than discovered afterwards.
  const pace = durationSec > 0 && km > 0
    ? `${Math.floor(durationSec / km / 60)}:${String(Math.round((durationSec / km) % 60)).padStart(2, '0')}`
    : null;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createActivity({
        name: name.trim(),
        sport_type: sport,
        // Sent without a zone: the server stores naive UTC, and appending one
        // here would shift every entry by the offset.
        start_time: when,
        duration_sec: durationSec,
        distance_meters: km > 0 ? Math.round(km * 1000) : null,
        avg_hr: numberOrNull(avgHr),
        max_hr: numberOrNull(maxHr),
        elevation_gain_m: numberOrNull(ascent),
        calories_kcal: numberOrNull(calories),
        steps: numberOrNull(steps),
        workout_tag: tag,
        notes: notes.trim() || null,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(describeError(err, 'Could not save that activity'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add an activity"
           subtitle="For a session that never reached your phone">
      <form onSubmit={save} className="space-y-4">
        <Field label="Name">
          <input className={input} value={name} placeholder="First 10k"
                 onChange={(e) => setName(e.target.value)} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Sport">
            <select className={input} value={sport} onChange={(e) => setSport(e.target.value)}>
              {SPORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Started">
            <input type="datetime-local" className={input} value={when}
                   max={nowLocal()} onChange={(e) => setWhen(e.target.value)} />
          </Field>
        </div>

        <div>
          <span className="text-2xs text-muted">Duration</span>
          <div className="mt-1 grid grid-cols-3 gap-2">
            {([['h', hours, setHours], ['min', minutes, setMinutes],
               ['sec', seconds, setSeconds]] as const).map(([label, value, set]) => (
              <div key={label}>
                <input type="number" min="0" className={input} value={value} placeholder="0"
                       onChange={(e) => set(e.target.value)} />
                <span className="block text-2xs text-faint mt-0.5 text-center">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Distance" hint="km">
            <input type="number" step="0.01" min="0" className={input} value={distanceKm}
                   placeholder="—" onChange={(e) => setDistanceKm(e.target.value)} />
          </Field>
          <Field label="Ascent" hint="m">
            <input type="number" min="0" className={input} value={ascent}
                   placeholder="—" onChange={(e) => setAscent(e.target.value)} />
          </Field>
        </div>

        {pace && (
          <p className="text-2xs text-muted">
            That works out at <span className="font-semibold text-fg tnum">{pace} /km</span>.
            Pace is not asked for because it follows from these two.
          </p>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Field label="Average HR" hint="bpm — sets the training load">
            <input type="number" min="25" max="250" className={input} value={avgHr}
                   placeholder="—" onChange={(e) => setAvgHr(e.target.value)} />
          </Field>
          <Field label="Maximum HR" hint="bpm">
            <input type="number" min="25" max="260" className={input} value={maxHr}
                   placeholder="—" onChange={(e) => setMaxHr(e.target.value)} />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Calories" hint="kcal">
            <input type="number" min="0" className={input} value={calories}
                   placeholder="—" onChange={(e) => setCalories(e.target.value)} />
          </Field>
          <Field label="Steps">
            <input type="number" min="0" className={input} value={steps}
                   placeholder="—" onChange={(e) => setSteps(e.target.value)} />
          </Field>
        </div>

        <div>
          <span className="text-2xs text-muted">Type of session</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <button key={t} type="button" onClick={() => setTag(tag === t ? null : t)}
                      className={`px-2.5 py-1 rounded-lg text-2xs font-semibold transition ${
                        tag === t ? 'bg-accent text-white'
                                  : 'bg-surface border border-line text-muted hover:text-fg'}`}>
                {TAG_LABELS[t] ?? t}
              </button>
            ))}
          </div>
        </div>

        <Field label="Notes">
          <textarea className={`${input} min-h-[4rem]`} value={notes}
                    placeholder="Anything the numbers miss"
                    onChange={(e) => setNotes(e.target.value)} />
        </Field>

        <p className="text-2xs text-faint">
          Training load is computed from your average heart rate, and without one it is left
          unavailable rather than guessed. Splits, best efforts, zones, grade-adjusted pace
          and decoupling all need a recording second by second, so this activity will not
          have them. It is marked as entered by hand.
        </p>

        {error && <p className="text-2xs text-negative">{error}</p>}

        <div className="flex items-center justify-end gap-2 pt-1">
          <button type="button" onClick={onClose}
                  className={`${button} text-muted hover:text-fg`}>Cancel</button>
          <button type="submit" disabled={saving || !name.trim() || durationSec <= 0}
                  className={`${button} bg-accent text-white hover:opacity-90`}>
            {saving ? 'Saving…' : 'Add activity'}
          </button>
        </div>
      </form>
    </Modal>
  );
};
