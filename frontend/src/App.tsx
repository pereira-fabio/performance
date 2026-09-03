import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { SummaryCards } from './components/SummaryCards';
import { PMCChart } from './components/PMCChart';
import { ActivityList } from './components/ActivityList';
import { ActivityDetail } from './components/ActivityDetail';
import { PersonalRecordsView } from './components/PersonalRecordsView';
import { SettingsModal } from './components/SettingsModal';
import { GPXUploadModal } from './components/GPXUploadModal';
import { Activity, DashboardSummary, PMCPoint, BestEffort } from './types';
import {
  getActivities,
  getActivityDetail,
  getDashboardSummary,
  getPMCData,
  getPersonalRecords,
  deleteActivity,
} from './api/client';
import { RefreshCw, Smartphone } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'activities' | 'pmc' | 'records'>('dashboard');
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [records, setRecords] = useState<BestEffort[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Modals
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const loadAllData = async () => {
    try {
      const [acts, sum, pmc, recs] = await Promise.all([
        getActivities(),
        getDashboardSummary(),
        getPMCData(90),
        getPersonalRecords(),
      ]);
      setActivities(acts);
      setSummary(sum);
      setPmcData(pmc);
      setRecords(recs);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const handleSelectActivity = async (act: Activity) => {
    try {
      const detail = await getActivityDetail(act.id);
      setSelectedActivity(detail);
    } catch (err) {
      console.error('Failed to load activity detail:', err);
    }
  };

  const handleDeleteActivity = async (id: string) => {
    try {
      await deleteActivity(id);
      setSelectedActivity(null);
      loadAllData();
    } catch (err) {
      alert('Failed to delete activity');
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadAllData();
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 flex flex-col font-sans">
      {/* Navigation Header */}
      <Navbar
        currentTab={currentTab}
        setCurrentTab={(tab) => {
          setSelectedActivity(null);
          setCurrentTab(tab);
        }}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenUpload={() => setIsUploadOpen(true)}
      />

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {selectedActivity ? (
          <ActivityDetail
            activity={selectedActivity}
            onBack={() => setSelectedActivity(null)}
            onDelete={handleDeleteActivity}
          />
        ) : (
          <>
            {/* Top Bar with Refresh */}
            <div className="flex items-center justify-between mb-5">
              <div>
                <h1 className="text-xl font-extrabold text-white tracking-tight">
                  {currentTab === 'dashboard' && 'Athlete Training Dashboard'}
                  {currentTab === 'activities' && 'All Workouts'}
                  {currentTab === 'pmc' && 'Fitness & Fatigue Performance Chart'}
                  {currentTab === 'records' && 'Personal Records Leaderboard'}
                </h1>
                <p className="text-xs text-gray-400 mt-0.5">
                  Real-time physiological tracking powered by Health Connect
                </p>
              </div>

              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs font-semibold text-gray-300 hover:text-white transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>

            {/* Dashboard View */}
            {currentTab === 'dashboard' && (
              <>
                <SummaryCards summary={summary} />
                <PMCChart data={pmcData} />
                <ActivityList
                  activities={activities}
                  onSelectActivity={handleSelectActivity}
                />
              </>
            )}

            {/* Activities View */}
            {currentTab === 'activities' && (
              <ActivityList
                activities={activities}
                onSelectActivity={handleSelectActivity}
              />
            )}

            {/* PMC View */}
            {currentTab === 'pmc' && (
              <>
                <SummaryCards summary={summary} />
                <PMCChart data={pmcData} />
              </>
            )}

            {/* Records View */}
            {currentTab === 'records' && (
              <PersonalRecordsView records={records} />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/80 bg-gray-950/60 py-6 text-center text-xs text-gray-500">
        <p>PeakPace Running Analytics · Self-hosted on Proxmox LXC & TrueNAS SCALE</p>
      </footer>

      {/* Modals */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onUpdated={loadAllData}
      />
      <GPXUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploaded={(act) => {
          loadAllData();
          handleSelectActivity(act);
        }}
      />
    </div>
  );
};
