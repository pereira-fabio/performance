import React, { useEffect, useState } from 'react';
import { Modal, button } from './Modal';
import { AdminAccount, AdminOverview, BackupFile } from '../types';
import {
  adminOverview, adminUsers, adminUpdateUser, adminDeleteUser,
  adminBackups, adminCreateBackup, adminPruneBackups,
} from '../api/client';
import { describeError } from '../lib/errors';

const when = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

export const AdminModal: React.FC<{
  isOpen: boolean; onClose: () => void; currentUserId?: string;
}> = ({ isOpen, onClose, currentUserId }) => {
  const [tab, setTab] = useState<'accounts' | 'backups'>('accounts');
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminAccount[]>([]);
  const [backups, setBackups] = useState<{ backups: BackupFile[]; total_mb: number;
    retention_days: number; count: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [o, u, b] = await Promise.all([adminOverview(), adminUsers(), adminBackups()]);
      setOverview(o); setUsers(u); setBackups(b); setNote(null);
    } catch (e) { setNote(describeError(e)); }
  };

  useEffect(() => { if (isOpen) refresh(); }, [isOpen]);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    setBusy(true); setNote(null);
    try { await fn(); await refresh(); setNote(msg); }
    catch (e) { setNote(describeError(e)); }
    finally { setBusy(false); setConfirmId(null); }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Server administration"
           subtitle="Accounts and backups">
      <div className="flex gap-1 p-1 mb-4 rounded-lg bg-surface border border-line">
        {(['accounts', 'backups'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-1.5 rounded-md text-[13px] font-medium capitalize transition ${
              tab === t ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
            {t}
          </button>
        ))}
      </div>

      {overview && (
        <div className="grid grid-cols-3 gap-3 mb-4 text-center">
          {[
            ['Accounts', overview.accounts],
            ['Activities', overview.activities],
            ['Database', `${overview.database_mb ?? '—'} MB`],
          ].map(([label, value]) => (
            <div key={String(label)} className="py-2 rounded-lg bg-surface border border-line">
              <div className="text-base font-bold tnum text-fg-strong">{value}</div>
              <div className="text-2xs text-muted">{label}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'accounts' && (
        <div className="divide-y divide-line border border-line rounded-lg overflow-hidden">
          {users.map((u) => (
            <div key={u.id} className="p-3">
              <div className="flex items-baseline justify-between gap-2">
                <div className="min-w-0">
                  <span className="text-[13px] font-semibold text-fg-strong">
                    {u.display_name || u.username}
                  </span>
                  {u.is_admin && (
                    <span className="ml-1.5 px-1.5 py-0.5 rounded text-2xs bg-accent-soft text-accent">
                      admin
                    </span>
                  )}
                  {!u.is_active && (
                    <span className="ml-1.5 px-1.5 py-0.5 rounded text-2xs bg-surface text-muted">
                      disabled
                    </span>
                  )}
                  {u.id === currentUserId && (
                    <span className="ml-1.5 text-2xs text-faint">you</span>
                  )}
                  <div className="text-2xs text-muted tnum">
                    {u.activities} activities · last {when(u.last_activity)} · joined {when(u.created_at)}
                  </div>
                </div>
              </div>

              {u.id !== currentUserId && (
                <div className="flex gap-2 mt-2">
                  <button disabled={busy}
                    onClick={() => act(() => adminUpdateUser(u.id, { is_active: !u.is_active }),
                                       u.is_active ? 'Account disabled.' : 'Account enabled.')}
                    className={`${button} text-2xs px-2 py-1 bg-surface border border-line text-fg`}>
                    {u.is_active ? 'Disable' : 'Enable'}
                  </button>
                  <button disabled={busy}
                    onClick={() => act(() => adminUpdateUser(u.id, { is_admin: !u.is_admin }),
                                       u.is_admin ? 'Admin removed.' : 'Admin granted.')}
                    className={`${button} text-2xs px-2 py-1 bg-surface border border-line text-fg`}>
                    {u.is_admin ? 'Remove admin' : 'Make admin'}
                  </button>
                  {confirmId === u.id ? (
                    <button disabled={busy}
                      onClick={() => act(() => adminDeleteUser(u.id), `${u.username} deleted.`)}
                      className={`${button} text-2xs px-2 py-1 bg-negative text-white`}>
                      Confirm delete
                    </button>
                  ) : (
                    <button disabled={busy} onClick={() => setConfirmId(u.id)}
                      className={`${button} text-2xs px-2 py-1 text-negative hover:bg-surface`}>
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'backups' && backups && (
        <div>
          <div className="flex gap-2 mb-3">
            <button disabled={busy} onClick={() => act(adminCreateBackup, 'Backup created.')}
              className={`${button} flex-1 bg-accent text-white hover:opacity-90`}>
              Back up now
            </button>
            <button disabled={busy} onClick={() => act(adminPruneBackups, 'Old backups pruned.')}
              className={`${button} flex-1 bg-surface border border-line text-fg`}>
              Prune old
            </button>
          </div>
          <p className="text-2xs text-muted mb-3">
            {backups.count} snapshots · {backups.total_mb} MB · kept for {backups.retention_days} days
          </p>
          <div className="divide-y divide-line border border-line rounded-lg max-h-56 overflow-y-auto">
            {backups.backups.map((b) => (
              <div key={b.name} className="flex items-baseline justify-between px-3 py-2 text-2xs">
                <span className="text-fg truncate">{b.name}</span>
                <span className="text-muted tnum shrink-0 ml-2">
                  {b.size_mb} MB · {b.age_days}d
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {note && <p className="mt-3 text-xs text-muted">{note}</p>}
    </Modal>
  );
};
