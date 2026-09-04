import React from 'react';
import { SportKey, TabKey, SPORTS } from '../lib/format';

export const Logo: React.FC<{ size?: number }> = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
    <rect width="32" height="32" rx="8" fill="var(--accent)" />
    <path d="M7 21.5 L12.5 14 L17 18 L25 8.5" stroke="#fff" strokeWidth="2.75"
          strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="25" cy="8.5" r="2.75" fill="#fff" />
  </svg>
);

const TABS: { key: TabKey; label: string; color: string }[] = [
  { key: 'home', label: 'Home', color: 'var(--accent)' },
  { key: 'runs', label: SPORTS.runs.label, color: SPORTS.runs.color },
  { key: 'walks', label: SPORTS.walks.label, color: SPORTS.walks.color },
  { key: 'gym', label: SPORTS.gym.label, color: SPORTS.gym.color },
];

interface ShellProps {
  tab: TabKey;
  onTab: (t: TabKey) => void;
  counts: Record<SportKey, number>;
  onMenu: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  /**
   * Controls belonging to a sub-view — Back, and whatever sits beside it.
   *
   * Rendered inside the sticky header rather than at the top of the page, so
   * leaving a long activity does not mean scrolling back up to find the way
   * out. Passed in rather than measured: sticking a row underneath the header
   * would need its exact height, which is a number that goes stale the moment
   * anything in the header changes.
   */
  toolbar?: React.ReactNode;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({
  tab, onTab, counts, onMenu, onRefresh, refreshing, toolbar, children,
}) => (
  <div className="min-h-screen bg-bg text-fg">
    <header className="sticky top-0 z-20 bg-bg/95 backdrop-blur border-b border-line">
      <div className="mx-auto max-w-content px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-1.5">
            <button onClick={onMenu} aria-label="Menu"
              className="p-2 -ml-2 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Logo size={22} />
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
          </div>
        </div>

        {/* Each sport is its own view; nothing is aggregated across them. */}
        <nav className="flex gap-1 -mb-px" role="tablist">
          {TABS.map(({ key, label, color }) => {
            const active = tab === key;
            const count = key === 'home' ? null : counts[key as SportKey];
            return (
              <button key={key} role="tab" aria-selected={active} onClick={() => onTab(key)}
                className={`relative px-3 py-3 text-sm font-semibold transition ${
                  active ? 'text-fg-strong' : 'text-muted hover:text-fg'}`}>
                {label}
                {count != null && (
                  <span className={`ml-1.5 text-xs font-medium ${active ? 'text-accent' : 'text-faint'}`}>
                    {count}
                  </span>
                )}
                {active && (
                  <span className="absolute inset-x-2 -bottom-px h-[3px] rounded-t-full"
                        style={{ background: color }} />
                )}
              </button>
            );
          })}
        </nav>

        {toolbar && (
          <div className="flex items-center justify-between gap-3 py-2 border-t border-line">
            {toolbar}
          </div>
        )}
      </div>
    </header>

    <main className="mx-auto max-w-content px-4 sm:px-6 py-6">{children}</main>

    <footer className="mx-auto max-w-content px-4 sm:px-6 pb-10 pt-6 text-xs text-faint">
      Self-hosted · your data never leaves your server
    </footer>
  </div>
);
