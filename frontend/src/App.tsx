import React, { useState, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { Shell } from './components/Shell';
import { SportView } from './components/SportView';
import { HomeView } from './components/HomeView';
import { PeriodRecap } from './components/PeriodRecap';
import { StatsView } from './components/StatsView';
import { EditActivityModal } from './components/EditActivityModal';
import { ActivityDetail } from './components/ActivityDetail';
import { SettingsModal } from './components/SettingsModal';
import { AppSettingsModal } from './components/AppSettingsModal';
import { Menu } from './components/Menu';
import { LoginScreen } from './components/LoginScreen';
import { AdminModal } from './components/AdminModal';
import { Activity, DashboardSummary, PMCPoint, BestEffort, HomeData } from './types';
import { SportKey, TabKey, bucketOf, isoWeekKey } from './lib/format';
import {
  getActivities, getActivityDetail, getDashboardSummary,
  getPMCData, getPersonalRecords, deleteActivity, getHome, getUserProfile,
  logout, setUnauthorizedHandler, refreshMe,
} from './api/client';
import { loadSession } from './lib/auth';
import { describeError } from './lib/errors';

/**
 * Back out of a sub-view.
 *
 * Declared here rather than inside App: a component defined in a render body is
 * a new type on every render, so React tears it down and rebuilds it each time
 * instead of updating it.
 */
const Back: React.FC<{ onClick: () => void; label: string }> = ({ onClick, label }) => (
  <button onClick={onClick}
          className="flex items-center gap-1.5 text-[13px] text-muted hover:text-fg transition">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
    </svg>
    {label}
  </button>
);

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
  const [recap, setRecap] = useState<'week' | 'month' | 'year' | null>(null);
  // Which week the recap opens on: the current one from the home page's own
  // panel, the last finished one from everywhere else.
  const [recapKey, setRecapKey] = useState<string | undefined>(undefined);
  const [statsOpen, setStatsOpen] = useState(false);
  const [editing, setEditing] = useState<Activity | null>(null);
  // Incremented whenever settings are saved, so views that read a setting
  // directly from the server pick the change up without a full reload.
  const [settingsSaves, setSettingsSaves] = useState(0);
  // Where the list was when a sub-view was opened from it. Null means "this
  // change should start at the top" rather than "restore nothing".
  const returnScroll = useRef<number | null>(null);
  // Where to go back to, remembered from when the sub-view was opened.
  const backTo = useRef(0);

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

  /**
   * Open one activity.
   *
   * `returnTo` is where Back should land, captured now rather than later: the
   * detail is fetched first, and by the time it arrives the position that made
   * sense is gone. Callers that arrive from somewhere other than the list pass
   * their own, because restoring one view's scroll onto another is worse than
   * starting at the top.
   */
  const openActivity = async (a: Activity, returnTo: number = window.scrollY) => {
    backTo.current = returnTo;
    returnScroll.current = null;
    try {
      setSelected(await getActivityDetail(a.id));
    } catch {
      setSelected(a);
    }
  };

  /**
   * Opening a page starts it at the top.
   *
   * These are separate pages that happen to share a URL, so the browser never
   * resets the scroll position for us: clicking a run near the bottom of a long
   * list opened its page already scrolled halfway down. Going back restores
   * where the list was, which is the reason you were down there.
   *
   * useLayoutEffect rather than useEffect so the jump happens before the
   * browser paints, instead of being visible as a flick.
   */
  useLayoutEffect(() => {
    if (returnScroll.current != null) {
      window.scrollTo(0, returnScroll.current);
      returnScroll.current = null;
    } else {
      window.scrollTo(0, 0);
    }
  }, [selected?.id, recap, statsOpen, tab]);

  const removeActivity = async (id: string) => {
    await deleteActivity(id);
    setSelected(null);
    load();
  };

  if (!session) {
    return <LoginScreen onSignedIn={() => setSession(loadSession())} />;
  }

  /**
   * One page at a time, but only one place that renders the frame.
   *
   * Each view used to return its own <Shell> and stop there, which left
   * the menu and every modal behind in the final return: from Stats, an
   * activity or a recap the hamburger set state that nothing was rendering,
   * and the menu only appeared once you had gone back.
   */
  let content: React.ReactNode;
  let toolbar: React.ReactNode = null;
  let onTabChange: (t: TabKey) => void = setTab;

  if (selected) {
    content = <ActivityDetail activity={selected} />;
    toolbar = (
      <>
        <Back label="Back"
              onClick={() => { returnScroll.current = backTo.current; setSelected(null); }} />
        {/* Edit rather than Delete: deleting is one of the things you might
            want to do to an activity, and the least common of them. */}
        <button onClick={() => setEditing(selected)}
                className="flex items-center gap-1.5 text-2xs font-semibold text-muted
                           hover:text-fg transition">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
          </svg>
          Edit
        </button>
      </>
    );
    onTabChange = (t) => { setSelected(null); setTab(t); };
  } else if (statsOpen) {
    content = (
      <StatsView data={home}
                 onSelectActivity={(id) => {
                   const found = activities.find((a) => a.id === id);
                   if (found) { setStatsOpen(false); openActivity(found, 0); }
                 }} />
    );
    toolbar = (
      <Back label="Back"
            onClick={() => { returnScroll.current = backTo.current; setStatsOpen(false); }} />
    );
    onTabChange = (t) => { setStatsOpen(false); setTab(t); };
  } else if (recap) {
    content = (
      <PeriodRecap kind={recap} initialKey={recapKey}
                   onSelectActivity={(id) => {
                     const found = activities.find((a) => a.id === id);
                     // Back from here lands on the list, which this reader
                     // never scrolled, so it starts at the top.
                     if (found) { setRecap(null); openActivity(found, 0); }
                   }} />
    );
    toolbar = (
      <Back label="Back"
            onClick={() => { returnScroll.current = backTo.current; setRecap(null); }} />
    );
    onTabChange = (t) => { setRecap(null); setTab(t); };
  } else {
    content = (
      <>
        {error && (
          <div className="mb-6 py-3 px-4 text-[13px] text-negative border border-line rounded-lg bg-surface">
            {error}
          </div>
        )}
        {tab === 'home' ? (
          <HomeView data={home}
                    onOpenThisWeek={() => {
                      backTo.current = window.scrollY;
                      setRecapKey(isoWeekKey());
                      setRecap('week');
                    }}
                    onOpenRecap={() => {
                      backTo.current = window.scrollY;
                      setRecapKey(undefined);
                      setRecap('week');
                    }}
                    cycleKey={settingsSaves} />
        ) : (
          <SportView tab={tab} activities={byTab[tab]} summary={summary}
                     pmc={pmc} records={records} onSelect={openActivity} />
        )}
      </>
    );
  }

  return (
    <>
      <Shell tab={tab} onTab={onTabChange} counts={counts}
             onMenu={() => setMenuOpen(true)} toolbar={toolbar}
             onRefresh={load} refreshing={refreshing}>
        {content}
      </Shell>

      <Menu open={menuOpen} onClose={() => setMenuOpen(false)} athlete={athlete}
            onProfile={() => { setMenuOpen(false); setProfileOpen(true); }}
            onSettings={() => { setMenuOpen(false); setSettingsOpen(true); }}
            onStats={() => {
              setMenuOpen(false);
              backTo.current = window.scrollY;
              setSelected(null);
              setRecap(null);
              setStatsOpen(true);
            }}
            isAdmin={session?.is_admin}
            onAdmin={() => { setMenuOpen(false); setAdminOpen(true); }} />
      {/* Bumps the same counter as app settings: uploading a picture has to
          refresh the level badge on the home page, which reads it directly. */}
      <EditActivityModal
        activity={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          // The open detail page is replaced with what the server returned, so
          // a corrected sport or name is visible without a round trip.
          setSelected((current) => (current && current.id === updated.id
            ? { ...current, ...updated } : current));
          setEditing(null);
          load();
        }}
        onDelete={(id) => { setEditing(null); removeActivity(id); }} />

      <SettingsModal isOpen={profileOpen} onClose={() => setProfileOpen(false)}
                     onUpdated={() => { setSettingsSaves((n) => n + 1); load(); }}
                     username={session?.username}
                     onSignOut={async () => { await logout(); setSession(null); }} />
      <AdminModal isOpen={adminOpen} onClose={() => setAdminOpen(false)}
                  currentUserId={session?.user_id} />
      <AppSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}
                        onUpdated={() => { setSettingsSaves((n) => n + 1); load(); }} activityCount={activities.length}
                        onDeleted={() => { setSettingsOpen(false); setSession(null); }}
                        dataSource={session?.data_source} />

    </>
  );
};
