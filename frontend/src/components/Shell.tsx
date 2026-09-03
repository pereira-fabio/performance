import React from 'react';
import { SportKey, SPORTS } from '../lib/format';

export const Logo: React.FC<{ size?: number }> = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
    <rect width="32" height="32" rx="8" fill="var(--accent)" />
    <path d="M7 21.5 L12.5 14 L17 18 L25 8.5" stroke="#fff" strokeWidth="2.75"
          strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="25" cy="8.5" r="2.75" fill="#fff" />
  </svg>
);

interface ShellProps {
  tab: SportKey;
  onTab: (t: SportKey) => void;
  counts: Record<SportKey, number>;
  onSettings: () => void;
  onUpload: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({
  tab, onTab, counts, onSettings, onUpload, onRefresh, refreshing, children,
}) => (
  <div className="min-h-screen bg-bg text-fg">
    <header className="sticky top-0 z-20 bg-bg/95 backdrop-blur border-b border-line">
      <div className="mx-auto max-w-content px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2.5">
            <Logo />
            <span className="text-base font-bold tracking-tight text-fg-strong">Performance</span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={onRefresh} disabled={refreshing} title="Refresh"
              className="p-2 rounded-lg text-muted hover:text-fg hover:bg-surface transition disabled:opacity-40">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round" className={refreshing ? 'animate-spin' : ''}>
                <path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" />
              </svg>
            </button>
            <button onClick={onUpload} title="Import GPX"
              className="p-2 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
              </svg>
            </button>
            <button onClick={onSettings} title="Settings"
              className="p-2 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.09A1.65 1.65 0 0 0 10.6 3.09V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.09A1.65 1.65 0 0 0 21 10.6h.09a2 2 0 0 1 0 4H21a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Each sport is its own view; nothing is aggregated across them. */}
        <nav className="flex gap-1 -mb-px" role="tablist">
          {(Object.keys(SPORTS) as SportKey[]).map((key) => {
            const active = tab === key;
            return (
              <button key={key} role="tab" aria-selected={active} onClick={() => onTab(key)}
                className={`relative px-3 py-3 text-sm font-semibold transition ${
                  active ? 'text-fg-strong' : 'text-muted hover:text-fg'}`}>
                {SPORTS[key].label}
                <span className={`ml-1.5 text-xs font-medium ${active ? 'text-accent' : 'text-faint'}`}>
                  {counts[key]}
                </span>
                {active && (
                  <span className="absolute inset-x-2 -bottom-px h-[3px] rounded-t-full"
                        style={{ background: SPORTS[key].color }} />
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>

    <main className="mx-auto max-w-content px-4 sm:px-6 py-6">{children}</main>

    <footer className="mx-auto max-w-content px-4 sm:px-6 pb-10 pt-6 text-xs text-faint">
      Self-hosted · your data never leaves your server
    </footer>
  </div>
);
