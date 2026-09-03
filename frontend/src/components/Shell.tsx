import React from 'react';
import { SportKey, SPORTS } from '../lib/format';

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
    <header className="sticky top-0 z-20 bg-bg/90 backdrop-blur border-b border-line">
      <div className="mx-auto max-w-content px-5">
        <div className="flex items-center justify-between h-14">
          <h1 className="text-[15px] font-semibold tracking-tight text-fg-strong">Performance</h1>
          <div className="flex items-center gap-1">
            <button onClick={onRefresh} disabled={refreshing}
              className="px-2.5 py-1.5 text-xs text-muted hover:text-fg transition disabled:opacity-40">
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
            <button onClick={onUpload}
              className="px-2.5 py-1.5 text-xs text-muted hover:text-fg transition">Import</button>
            <button onClick={onSettings}
              className="px-2.5 py-1.5 text-xs text-muted hover:text-fg transition">Settings</button>
          </div>
        </div>

        {/* Each sport is its own view; nothing is aggregated across them. */}
        <nav className="flex gap-6 -mb-px overflow-x-auto no-scrollbar" role="tablist">
          {(Object.keys(SPORTS) as SportKey[]).map((key) => {
            const active = tab === key;
            return (
              <button
                key={key}
                role="tab"
                aria-selected={active}
                onClick={() => onTab(key)}
                className={`relative py-2.5 text-[13px] whitespace-nowrap transition ${
                  active ? 'text-fg-strong font-medium' : 'text-muted hover:text-fg'
                }`}
              >
                {SPORTS[key].label}
                <span className="ml-1.5 text-2xs text-faint tnum">{counts[key]}</span>
                {active && (
                  <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full"
                        style={{ background: SPORTS[key].color }} />
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>

    <main className="mx-auto max-w-content px-5 py-8">{children}</main>

    <footer className="mx-auto max-w-content px-5 pb-10 pt-4 text-2xs text-faint border-t border-line">
      Self-hosted · data stays on your server
    </footer>
  </div>
);
