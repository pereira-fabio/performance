import React, { useEffect, useState } from 'react';
import { DeviceConnection, getConnection, connectGarmin, disconnectDevice, syncConnection }
  from '../api/client';
import { input, button } from './Modal';
import { describeError } from '../lib/errors';

const ago = (iso?: string | null) => {
  if (!iso) return 'never';
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
};

export const ConnectionCard: React.FC<{ onChanged: () => void }> = ({ onChanged }) => {
  const [conn, setConn] = useState<DeviceConnection | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfa, setMfa] = useState('');
  const [needsMfa, setNeedsMfa] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = () => getConnection().then(setConn).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const link = async () => {
    setBusy(true); setNote(null);
    try {
      setConn(await connectGarmin(email, password, mfa || undefined));
      setPassword(''); setMfa(''); setNeedsMfa(false);
      setNote('Connected. Your activities will arrive on their own from now on.');
      onChanged();
    } catch (e: any) {
      const msg = describeError(e, 'Could not connect.');
      // Garmin asks for a code only once it has accepted the password.
      if (/two-factor|mfa|code/i.test(msg)) setNeedsMfa(true);
      setNote(msg);
    } finally { setBusy(false); }
  };

  if (conn) {
    return (
      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-fg-strong capitalize">
              {conn.provider} connected
            </div>
            <div className="text-2xs text-muted truncate">{conn.account_label}</div>
            <div className={`text-2xs mt-0.5 ${conn.last_ok ? 'text-muted' : 'text-negative'}`}>
              Last sync {ago(conn.last_synced_at)}
              {conn.last_status ? ` · ${conn.last_status}` : ''}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button disabled={busy}
            onClick={async () => {
              setBusy(true); setNote(null);
              try { const r = await syncConnection(); setNote(r.message); await refresh(); onChanged(); }
              catch (e) { setNote(describeError(e, 'Sync failed.')); }
              finally { setBusy(false); }
            }}
            className={`${button} flex-1 bg-accent text-white hover:opacity-90`}>
            {busy ? 'Syncing…' : 'Sync now'}
          </button>
          <button disabled={busy}
            onClick={async () => {
              setBusy(true);
              try { await disconnectDevice(); setConn(null); setNote('Disconnected.'); onChanged(); }
              finally { setBusy(false); }
            }}
            className={`${button} text-muted hover:text-negative`}>
            Disconnect
          </button>
        </div>
        {note && <p className="text-2xs text-muted">{note}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-2xs text-muted">
        Sign in with your Garmin Connect account and new activities will be pulled in
        automatically, roughly every half hour. Your password is used once to obtain a
        session and is not stored.
      </p>
      <input className={input} placeholder="Garmin Connect email" autoComplete="username"
             value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className={input} type="password" placeholder="Password" autoComplete="current-password"
             value={password} onChange={(e) => setPassword(e.target.value)} />
      {needsMfa && (
        <input className={input} placeholder="Two-factor code" value={mfa}
               onChange={(e) => setMfa(e.target.value)} />
      )}
      <button disabled={busy || !email || !password}
              onClick={link}
              className={`${button} w-full bg-accent text-white hover:opacity-90`}>
        {busy ? 'Connecting…' : needsMfa ? 'Verify code' : 'Connect Garmin'}
      </button>
      {note && <p className="text-2xs text-muted">{note}</p>}
    </div>
  );
};
