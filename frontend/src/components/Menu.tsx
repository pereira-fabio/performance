import React, { useEffect } from 'react';
import { Logo } from './Shell';

interface MenuProps {
  open: boolean;
  onClose: () => void;
  onProfile: () => void;
  onSettings: () => void;
  onStats: () => void;
  onImport: () => void;
  athlete?: string;
  isAdmin?: boolean;
  dataSource?: string;
  onAdmin: () => void;
  onSignOut: () => void;
}

const Item: React.FC<{ label: string; hint?: string; icon: React.ReactNode; onClick: () => void }> = ({
  label, hint, icon, onClick,
}) => (
  <button onClick={onClick}
    className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-surface transition-colors">
    <span className="shrink-0 text-muted">{icon}</span>
    <span className="min-w-0">
      <span className="block text-sm font-medium text-fg-strong">{label}</span>
      {hint && <span className="block text-xs text-muted truncate">{hint}</span>}
    </span>
  </button>
);

const svg = (d: string) => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{d.split('|').map((p, i) =>
    <path key={i} d={p} />)}</svg>
);

export const Menu: React.FC<MenuProps> = ({
  open, onClose, onProfile, onSettings, onStats, onImport, onAdmin, onSignOut,
  athlete, isAdmin, dataSource,
}) => {
  // Escape should close an overlay; without it the only way out is the mouse.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <nav
        className="relative w-72 max-w-[85vw] bg-bg border-r border-line h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-5 border-b border-line flex items-center gap-2.5">
          <Logo size={24} />
          <div className="min-w-0">
            <div className="text-sm font-bold text-fg-strong">Performance</div>
            {athlete && <div className="text-xs text-muted truncate">{athlete}</div>}
          </div>
        </div>

        <div className="py-2">
          <Item label="Stats" hint="Totals, profile and printable reports"
                icon={svg('M3 3v18h18|M7 15l4-5 3 3 4-6')}
                onClick={onStats} />
          <Item label="Profile" hint="Heart rate, thresholds, weight"
                icon={svg('M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2|M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8')}
                onClick={onProfile} />
          <Item label="Settings" hint="Appearance and maintenance"
                icon={svg('M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6|M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-2.82 1.17V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 7.26 19.4l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 3 12.91V12a2 2 0 0 1 4 0')}
                onClick={onSettings} />
          {isAdmin && (
            <Item label="Administration" hint="Accounts and backups"
                  icon={svg('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z')}
                  onClick={onAdmin} />
          )}
          <Item label="Import activities"
                hint={dataSource === 'file_import' ? 'Garmin, Polar or Coros files' : 'GPX, TCX, FIT or a zip'}
                icon={svg('M12 16V4|M7 9l5-5 5 5|M4 20h16')}
                onClick={onImport} />
        </div>

        <div className="mt-auto border-t border-line">
          <Item label="Sign out" icon={svg('M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4|M16 17l5-5-5-5|M21 12H9')}
                onClick={onSignOut} />
          <div className="px-5 pb-4 text-xs text-faint">
            Self-hosted · your data stays on your server
          </div>
        </div>
      </nav>
    </div>
  );
};
