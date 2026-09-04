import React, { useEffect, useState } from 'react';
import { Logo } from './Shell';
import { getAuthStatus, login, register, AuthStatus } from '../api/client';
import { input, button } from './Modal';
import { describeError } from '../lib/errors';

export const LoginScreen: React.FC<{ onSignedIn: () => void }> = ({ onSignedIn }) => {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [source, setSource] = useState('health_connect');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuthStatus()
      .then((s) => {
        setStatus(s);
        // Nobody has registered yet, so there is nothing to sign in to.
        if (!s.has_accounts) setMode('register');
      })
      .catch((err) => setError(describeError(err)));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'register') await register(username, password, username, source);
      else await login(username, password);
      onSignedIn();
    } catch (err: any) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const firstAccount = status && !status.has_accounts;

  return (
    <div className="min-h-screen bg-bg text-fg flex items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-7">
          <Logo size={30} />
          <span className="text-xl font-bold tracking-tight text-fg-strong">Performance</span>
        </div>

        {firstAccount && (
          <div className="mb-5 p-4 rounded-xl bg-accent-soft border border-line text-[13px]">
            <p className="font-semibold text-fg-strong">Set up your account</p>
            <p className="text-muted mt-1">
              {status!.unclaimed_activities > 0
                ? `This server already holds ${status!.unclaimed_activities} activities. ` +
                  'The first account created takes ownership of them.'
                : 'Everyone on this server signs in separately and sees only their own training.'}
            </p>
          </div>
        )}

        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="text-xs text-muted">Username</span>
            <input className={input} value={username} autoComplete="username" autoFocus
                   onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label className="block">
            <span className="text-xs text-muted">Password</span>
            <input className={input} type="password" value={password}
                   autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                   onChange={(e) => setPassword(e.target.value)} />
            {mode === 'register' && (
              <span className="block text-2xs text-faint mt-1">At least 8 characters.</span>
            )}
          </label>

          {mode === 'register' && (
            <div>
              <span className="text-xs text-muted">Where your training comes from</span>
              <div className="mt-1.5 space-y-2">
                {[
                  { id: 'health_connect', title: 'Android phone',
                    hint: 'Reads Health Connect through the companion app — Nothing X, Samsung Health, Fitbit and others.' },
                  { id: 'file_import', title: 'Garmin, Polar, Coros or iPhone',
                    hint: 'No Health Connect. Link your Garmin account for automatic sync, or import exported files.' },
                ].map((opt) => (
                  <button type="button" key={opt.id} onClick={() => setSource(opt.id)}
                    className={`w-full text-left p-3 rounded-lg border transition ${
                      source === opt.id
                        ? 'border-accent bg-accent-soft'
                        : 'border-line hover:border-line-strong'}`}>
                    <div className="text-[13px] font-semibold text-fg-strong">{opt.title}</div>
                    <div className="text-2xs text-muted mt-0.5">{opt.hint}</div>
                  </button>
                ))}
              </div>
              <p className="text-2xs text-faint mt-1.5">You can change this later.</p>
            </div>
          )}

          {error && <p className="text-[13px] text-negative">{error}</p>}

          <button type="submit" disabled={busy || !username || !password}
                  className={`${button} w-full bg-accent text-white hover:opacity-90`}>
            {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}
          </button>
        </form>

        {!firstAccount && (
          <p className="mt-5 text-center text-[13px] text-muted">
            {mode === 'login' ? 'New here?' : 'Already have an account?'}{' '}
            <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}
                    className="text-accent font-medium hover:underline">
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        )}

        <p className="mt-8 text-center text-2xs text-faint">
          Self-hosted · accounts are stored on your own server
        </p>
      </div>
    </div>
  );
};
