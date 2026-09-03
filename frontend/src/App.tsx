import React, { useState, useEffect, useMemo } from 'react';
import { Shell } from './components/Shell';
import { SportView } from './components/SportView';
import { HomeView } from './components/HomeView';
import { ActivityDetail } from './components/ActivityDetail';
import { SettingsModal } from './components/SettingsModal';
import { AppSettingsModal } from './components/AppSettingsModal';
import { Menu } from './components/Menu';
import { GPXUploadModal } from './components/GPXUploadModal';
import { Activity, DashboardSummary, PMCPoint, BestEffort, HomeData } from './types';
import { SportKey, TabKey, bucketOf } from './lib/format';
import {
  getActivities, getActivityDetail, getDashboardSummary,
  getPMCData, getPersonalRecords, deleteActivity, getHome, getUserProfile,
} from './api/client';

export const App: React.FC = () => {
  const [tab, setTab] = useState<TabKey>('home');
  const [selected, setSelected] = useState<Activity | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [pmc, setPmc] = useState<PMCPoint[]>([]);
  const [records, setRecords] = useState<BestEffort[]>([]);
  const [home, setHome] = useState<HomeData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [athlete, setAthlete] = useState<string | undefined>();
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try {
      const [acts, sum, pm, recs, hm] = await Promise.all([
        getActivities(), getDashboardSummary(), getPMCData(180), getPersonalRecords(), getHome(),
      ]);
      setActivities(acts);
      setSummary(sum);
      setPmc(pm);
      setRecords(recs);
      setHome(hm);
      getUserProfile().then((p) => setAthlete(p.name)).catch(() => {});
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? 'Could not reach the server');
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  // The Android app opens these views by loading the page with a fragment,
  // so the same screens are reachable from its menu without duplicating them.
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes('profile')) setProfileOpen(true);
    else if (hash.includes('settings')) setSettingsOpen(true);
  }, []);

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
             onMenu={() => setMenuOpen(true)}
             onRefresh={load} refreshing={refreshing}>
        <ActivityDetail activity={selected} onBack={() => setSelected(null)} onDelete={removeActivity} />
      </Shell>
    );
  }

  return (
    <>
      <Shell tab={tab} onTab={setTab} counts={counts}
             onMenu={() => setMenuOpen(true)}
             onRefresh={load} refreshing={refreshing}>
        {error && (
          <div className="mb-6 py-3 px-4 text-[13px] text-negative border border-line rounded-lg bg-surface">
            {error}
          </div>
        )}
        {tab === 'home' ? (
          <HomeView data={home} onTab={setTab} />
        ) : (
          <SportView tab={tab} activities={byTab[tab]} summary={summary}
                     pmc={pmc} records={records} onSelect={openActivity} />
        )}
      </Shell>

      <Menu open={menuOpen} onClose={() => setMenuOpen(false)} athlete={athlete}
            onProfile={() => { setMenuOpen(false); setProfileOpen(true); }}
            onSettings={() => { setMenuOpen(false); setSettingsOpen(true); }}
            onImport={() => { setMenuOpen(false); setUploadOpen(true); }} />
      <SettingsModal isOpen={profileOpen} onClose={() => setProfileOpen(false)} onUpdated={load} />
      <AppSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}
                        onUpdated={load} activityCount={activities.length} />
      <GPXUploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)}
                      onUploaded={(a) => { load(); openActivity(a); }} />
    </>
  );
};
