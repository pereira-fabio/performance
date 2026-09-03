import React, { useState } from 'react';
import { PMCPoint } from '../types';
import {
  ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';

const RANGES = [30, 90, 180] as const;

export const PMCChart: React.FC<{ data: PMCPoint[] }> = ({ data }) => {
  const [range, setRange] = useState<(typeof RANGES)[number]>(90);
  const shown = data.slice(-range);

  return (
    <div>
      <div className="flex justify-end gap-3 mb-3">
        {RANGES.map((r) => (
          <button key={r} onClick={() => setRange(r)}
            className={`text-2xs transition ${r === range ? 'text-fg-strong font-medium' : 'text-faint hover:text-muted'}`}>
            {r}d
          </button>
        ))}
      </div>

      <div className="h-56 -ml-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={shown} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false}
              tick={{ fontSize: 10, fill: 'var(--faint)' }} minTickGap={40}
              tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })} />
            <YAxis yAxisId="load" tickLine={false} axisLine={false} width={32}
              tick={{ fontSize: 10, fill: 'var(--faint)' }} />
            <Tooltip
              contentStyle={{
                background: 'var(--bg)', border: '1px solid var(--line-strong)',
                borderRadius: 8, fontSize: 12, color: 'var(--fg)', boxShadow: 'none',
              }}
              labelFormatter={(v) => new Date(v).toLocaleDateString(undefined,
                { weekday: 'short', day: 'numeric', month: 'long' })} />
            <ReferenceLine yAxisId="load" y={0} stroke="var(--line-strong)" />

            <Bar yAxisId="load" dataKey="daily_tss" name="Load" fill="var(--line-strong)" barSize={3} />
            <Line yAxisId="load" type="monotone" dataKey="ctl" name="Fitness"
                  stroke="var(--run)" strokeWidth={1.75} dot={false} />
            <Line yAxisId="load" type="monotone" dataKey="atl" name="Fatigue"
                  stroke="var(--caution)" strokeWidth={1.25} dot={false} strokeDasharray="3 3" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="flex gap-5 mt-3 text-2xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-px" style={{ background: 'var(--run)' }} />Fitness
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 border-t border-dashed" style={{ borderColor: 'var(--caution)' }} />Fatigue
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-2.5 bg-line-strong" />Daily load
        </span>
      </div>
    </div>
  );
};
