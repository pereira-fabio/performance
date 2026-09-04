import React, { useState, useEffect, useMemo } from 'react';
import { Shell } from './components/Shell';
import { SportView } from './components/SportView';
import { HomeView } from './components/HomeView';
import { ActivityDetail } from './components/ActivityDetail';
import { SettingsModal } from './components/SettingsModal';
import { AppSettingsModal } from './components/AppSettingsModal';
import { Menu } from './components/Menu';
import { LoginScreen } from './components/LoginScreen';
import { AdminModal } from './components/AdminModal';
import { GPXUploadModal } from './components/GPXUploadModal';
import { Activity, DashboardSummary, PMCPoint, BestEffort, HomeData } from './types';
import { SportKey, TabKey, bucketOf } from './lib/format';
import {
  getActivities, getActivityDetail, getDashboardSummary,
  getPMCData, getPersonalRecords, deleteActivity, getHome, getUserProfile,
  logout, setUnauthorizedHandler, refreshMe,
} from './api/client';
import { loadSession } from './lib/auth';
import { describeError } from './lib/errors';

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
  const [adminOpen, setAdminOpen] = useState(false);
  const [athlete, setAthlete] = useState<string | undefined>();
  const [session, setSession] = useState(() => loadSession());
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
      // Picks up fields a session predating them would otherwise never see.
      // Only replaces the stored session when something actually differs:
      // loadSession() builds a new object every call, and setting it
      // unconditionally would retrigger the effect that called this.
      refreshMe()
        .then((me) => {
          setSession((prev) =>
            prev && prev.is_admin === me.is_admin && prev.user_id === me.user_id
              ? prev
              : loadSession()
          );
        })
        .catch(() => {});
      setError(null);
    } catch (err: any) {
      setError(describeError(err, 'Could not load your data'));
    } finally {
      setRefreshing(false);
    }
  };

  // A rejected session drops straight back to sign-in rather than leaving the
  // dashboard sitting there failing every request.
  useEffect(() => { setUnauthorizedHandler(() => setSession(null)); }, []);

  // Keyed on the token, not the session object: the object is rebuilt on every
  // read, so depending on it reloads endlessly.
  useEffect(() => { if (session?.token) load(); }, [session?.token]);

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

  if (!session) {
    return <LoginScreen onSignedIn={() => setSession(loadSession())} />;
  }

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
            isAdmin={session?.is_admin}
            onAdmin={() => { setMenuOpen(false); setAdminOpen(true); }}
            onImport={() => { setMenuOpen(false); setUploadOpen(true); }}
            onSignOut={async () => { await logout(); setSession(null); }} />
      <SettingsModal isOpen={profileOpen} onClose={() => setProfileOpen(false)} onUpdated={load} />
      <AdminModal isOpen={adminOpen} onClose={() => setAdminOpen(false)}
                  currentUserId={session?.user_id} />
      <AppSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}
                        onUpdated={load} activityCount={activities.length}
                        onDeleted={() => { setSettingsOpen(false); setSession(null); }} />
      <GPXUploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)}
                      onUploaded={(a) => { load(); openActivity(a); }} />
    </>
  );
};
