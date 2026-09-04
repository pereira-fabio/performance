import React, { useEffect, useState } from 'react';
import { CoachNote as Note, getPeriodNote } from '../api/client';
import { Card } from './Stat';

/**
 * The coach's review of a finished period.
 *
 * Loaded separately from the recap it sits in, so the figures appear at once
 * and the writing catches up: a local model takes seconds, and blocking the
 * whole page on it would make the recap feel broken.
 */
export const PeriodNoteCard: React.FC<{
  kind: 'week' | 'month' | 'year';
  offset?: number;
  periodKey?: string;
}> = ({ kind, offset = 0, periodKey }) => {
  const [note, setNote] = useState<Note | null>(null);
  const [busy, setBusy] = useState(true);

  const load = async (refresh = false) => {
    setBusy(true);
    try {
      setNote(await getPeriodNote(kind, periodKey, offset, refresh));
    } catch {
      setNote({ available: false, reason: 'The coach could not be reached.' });
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [kind, offset, periodKey]);

  if (!busy && (!note || !note.available)) return null;

  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h2 className="text-sm font-bold text-fg-strong tracking-tight">Your coach on this {kind}</h2>
        {note?.available && (
          <button onClick={() => load(true)} disabled={busy}
                  className="text-2xs text-faint hover:text-muted transition disabled:opacity-50">
            {busy ? 'Writing…' : 'Rewrite'}
          </button>
        )}
      </div>
      <Card className="p-5">
        {busy && !note?.text ? (
          <p className="text-[13px] text-muted">Reading your {kind}…</p>
        ) : (
          <>
            <p className="text-[13px] leading-relaxed text-fg whitespace-pre-line">{note?.text}</p>
            <p className="mt-3 pt-3 border-t border-line text-2xs text-faint">
              Written by {note?.model ?? 'a language model'} running on your own server, from the
              figures on this page. It phrases them; it does not measure anything.
            </p>
          </>
        )}
      </Card>
    </section>
  );
};
