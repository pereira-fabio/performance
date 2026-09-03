import React, { useState, useEffect, useMemo } from 'react';
import { Shell } from './components/Shell';
import { SportView } from './components/SportView';
import { ActivityDetail } from './components/ActivityDetail';
import { SettingsModal } from './components/SettingsModal';
import { GPXUploadModal } from './components/GPXUploadModal';
import { Activity, DashboardSummary, PMCPoint, BestEffort } from './types';
import { SportKey, bucketOf } from './lib/format';
import {
  getActivities, getActivityDetail, getDashboardSummary,
  getPMCData, getPersonalRecords, deleteActivity,
} from './api/client';

export const App: React.FC = () => {
  const [tab, setTab] = useState<SportKey>('runs');
  const [selected, setSelected] = useState<Activity | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [pmc, setPmc] = useState<PMCPoint[]>([]);
  const [records, setRecords] = useState<BestEffort[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try {
      const [acts, sum, pm, recs] = await Promise.all([
        getActivities(), getDashboardSummary(), getPMCData(180), getPersonalRecords(),
      ]);
      setActivities(acts);
      setSummary(sum);
      setPmc(pm);
      setRecords(recs);
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? 'Could not reach the server');
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Activities are bucketed once and reused, so switching tabs is instant and
  // no sport's figures can leak into another's.
  const byTab = useMemo(() => {
    const groups: Record<SportKey, Activity[]> = { runs: [], walks: [], gym: [] };
    for (const a of activities) groups[bucketOf(a)].push(a);
    return groups;
  }, [activities]);

  const counts = useMemo(
    () => ({ runs: byTab.runs.length, walks: byTab.walks.length, gym: byTab.gym.length }),
    [byTab]
  );

  const openActivity = async (a: Activity) => {
    try {
      setSelected(await getActivityDetail(a.id));
    } catch {
      setSelected(a);
    }
  };

  const removeActivity = async (id: string) => {
    await deleteActivity(id);
    setSelected(null);
    load();
  };

  if (selected) {
    return (
      <Shell tab={tab} onTab={(t) => { setSelected(null); setTab(t); }} counts={counts}
             onSettings={() => setSettingsOpen(true)} onUpload={() => setUploadOpen(true)}
             onRefresh={load} refreshing={refreshing}>
        <ActivityDetail activity={selected} onBack={() => setSelected(null)} onDelete={removeActivity} />
      </Shell>
    );
  }

  return (
    <>
      <Shell tab={tab} onTab={setTab} counts={counts}
             onSettings={() => setSettingsOpen(true)} onUpload={() => setUploadOpen(true)}
             onRefresh={load} refreshing={refreshing}>
        {error && (
          <div className="mb-6 py-3 px-4 text-[13px] text-negative border border-line rounded-lg bg-surface">
            {error}
          </div>
        )}
        <SportView tab={tab} activities={byTab[tab]} summary={summary}
                   pmc={pmc} records={records} onSelect={openActivity} />
      </Shell>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} onUpdated={load} />
      <GPXUploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)}
                      onUploaded={(a) => { load(); openActivity(a); }} />
    </>
  );
};
