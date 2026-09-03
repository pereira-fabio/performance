import React, { useState } from 'react';
import { PMCPoint } from '../types';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface PMCChartProps {
  data: PMCPoint[];
}

export const PMCChart: React.FC<PMCChartProps> = ({ data }) => {
  const [timeRange, setTimeRange] = useState<30 | 60 | 90 | 180>(90);

  const filteredData = data.slice(-timeRange);

  return (
    <div className="bg-gray-900/90 backdrop-blur border border-gray-800/80 rounded-2xl p-5 shadow-lg mb-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-gray-800 gap-3">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center space-x-2">
            <span>Performance Management Chart (PMC)</span>
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Banister Impulse-Response Model: Track Fitness (CTL), Fatigue (ATL), and Form (TSB)
          </p>
        </div>

        {/* Time Filter Buttons */}
        <div className="flex items-center space-x-1 bg-gray-950 p-1 rounded-xl border border-gray-800">
          {([30, 60, 90, 180] as const).map((days) => (
            <button
              key={days}
              onClick={() => setTimeRange(days)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                timeRange === days
                  ? 'bg-cyan-500 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {days}D
            </button>
          ))}
        </div>
      </div>

      {filteredData.length === 0 ? (
        <div className="h-72 flex items-center justify-center text-gray-500 text-sm">
          No training data recorded yet. Sync runs from your phone or import a GPX file to generate your PMC curve.
        </div>
      ) : (
        <div className="h-80 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={filteredData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tssGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.8} />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              
              <XAxis
                dataKey="date"
                stroke="#64748b"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickFormatter={(val) => {
                  try {
                    return format(parseISO(val), 'MMM d');
                  } catch {
                    return val;
                  }
                }}
              />
              
              <YAxis
                yAxisId="load"
                stroke="#64748b"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
              />
              
              <YAxis
                yAxisId="tsb"
                orientation="right"
                stroke="#64748b"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
              />
              
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  fontSize: '12px',
                  color: '#f8fafc',
                }}
                labelFormatter={(label) => {
                  try {
                    return format(parseISO(label), 'EEEE, MMMM d, yyyy');
                  } catch {
                    return label;
                  }
                }}
              />
              <Legend
                verticalAlign="top"
                height={36}
                wrapperStyle={{ fontSize: '12px', paddingTop: '0px' }}
              />
              
              <ReferenceLine yAxisId="tsb" y={0} stroke="#475569" strokeDasharray="3 3" />
              <ReferenceLine yAxisId="tsb" y={10} stroke="#10b981" strokeDasharray="2 2" />
              <ReferenceLine yAxisId="tsb" y={-20} stroke="#f43f5e" strokeDasharray="2 2" />

              {/* Daily TSS Bars */}
              <Bar
                yAxisId="load"
                dataKey="daily_tss"
                name="Daily TSS"
                fill="url(#tssGradient)"
                barSize={6}
                radius={[2, 2, 0, 0]}
              />

              {/* CTL - Fitness (42d EWMA) */}
              <Line
                yAxisId="load"
                type="monotone"
                dataKey="ctl"
                name="Fitness (CTL 42d)"
                stroke="#06b6d4"
                strokeWidth={2.5}
                dot={false}
              />

              {/* ATL - Fatigue (7d EWMA) */}
              <Line
                yAxisId="load"
                type="monotone"
                dataKey="atl"
                name="Fatigue (ATL 7d)"
                stroke="#f43f5e"
                strokeWidth={2}
                dot={false}
              />

              {/* TSB - Form (CTL - ATL) */}
              <Line
                yAxisId="tsb"
                type="monotone"
                dataKey="tsb"
                name="Form (TSB)"
                stroke="#eab308"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
