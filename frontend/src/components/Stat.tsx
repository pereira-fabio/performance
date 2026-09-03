import React from 'react';

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({
  className = '', children,
}) => (
  <div className={`bg-card border border-line rounded-xl shadow-card ${className}`}>{children}</div>
);

interface StatProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  sub?: string;
  tone?: 'default' | 'positive' | 'caution' | 'negative' | 'accent';
  /** Explains an absent value, so a dash is never merely blank. */
  title?: string;
  large?: boolean;
}

const tones: Record<string, string> = {
  default: 'text-fg-strong',
  accent: 'text-accent',
  positive: 'text-positive',
  caution: 'text-caution',
  negative: 'text-negative',
};

export const Stat: React.FC<StatProps> = ({
  label, value, unit, sub, tone = 'default', title, large,
}) => (
  <div title={title}>
    <div className="text-xs font-medium uppercase tracking-wide text-faint">{label}</div>
    <div className="mt-1 flex items-baseline gap-1">
      <span className={`${large ? 'text-4xl' : 'text-2xl'} font-bold tnum tracking-tight ${tones[tone]}`}>
        {value}
      </span>
      {unit && <span className="text-sm font-medium text-muted">{unit}</span>}
    </div>
    {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
  </div>
);

export const StatGrid: React.FC<{ children: React.ReactNode; cols?: 2 | 3 | 4 }> = ({
  children, cols = 4,
}) => {
  // Tailwind scans for literal class names, so these are whole strings rather
  // than interpolated -- an interpolated class is never generated.
  const map = { 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3', 4: 'sm:grid-cols-4' };
  return <div className={`grid grid-cols-2 ${map[cols]} gap-5 p-5`}>{children}</div>;
};

export const Section: React.FC<{
  title: string; aside?: React.ReactNode; children: React.ReactNode; flush?: boolean;
}> = ({ title, aside, children, flush }) => (
  <section className="mt-6">
    <div className="flex items-baseline justify-between mb-3 px-1">
      <h2 className="text-sm font-bold text-fg-strong tracking-tight">{title}</h2>
      {aside}
    </div>
    <Card className={flush ? '' : 'p-5'}>{children}</Card>
  </section>
);

export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="py-12 text-center text-sm text-muted">{children}</p>
);
