import React from 'react';

interface StatProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  sub?: string;
  tone?: 'default' | 'positive' | 'caution' | 'negative';
  /** Shown when the value is absent, so a dash is never unexplained. */
  title?: string;
}

const tones: Record<string, string> = {
  default: 'text-fg-strong',
  positive: 'text-positive',
  caution: 'text-caution',
  negative: 'text-negative',
};

export const Stat: React.FC<StatProps> = ({ label, value, unit, sub, tone = 'default', title }) => (
  <div title={title}>
    <div className="text-2xs uppercase tracking-wider text-faint">{label}</div>
    <div className="mt-1 flex items-baseline gap-1">
      <span className={`text-2xl font-semibold tnum tracking-tight ${tones[tone]}`}>{value}</span>
      {unit && <span className="text-xs text-muted">{unit}</span>}
    </div>
    {sub && <div className="mt-0.5 text-2xs text-muted">{sub}</div>}
  </div>
);

// Tailwind scans source for literal class names, so the column count maps to
// whole classes rather than being interpolated -- an interpolated one is never
// generated and silently does nothing.
const COLS: Record<number, string> = {
  2: 'sm:grid-cols-2',
  3: 'sm:grid-cols-3',
  4: 'sm:grid-cols-4',
};

export const StatRow: React.FC<{ children: React.ReactNode; cols?: 2 | 3 | 4 }> = ({ children, cols = 4 }) => (
  <div className={`grid gap-x-6 gap-y-6 grid-cols-2 ${COLS[cols]} py-6 border-b border-line`}>
    {children}
  </div>
);

export const Section: React.FC<{ title: string; aside?: React.ReactNode; children: React.ReactNode }> = ({
  title, aside, children,
}) => (
  <section className="py-7 border-b border-line last:border-0">
    <div className="flex items-baseline justify-between mb-4">
      <h2 className="text-[13px] font-medium text-fg-strong">{title}</h2>
      {aside}
    </div>
    {children}
  </section>
);

export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="py-10 text-center text-[13px] text-muted">{children}</p>
);
