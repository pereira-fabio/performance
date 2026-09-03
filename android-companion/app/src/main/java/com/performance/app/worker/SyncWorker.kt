package com.performance.app.worker

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.performance.app.data.HealthConnectManager
import com.performance.app.data.SyncApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class SyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val prefs = applicationContext.getSharedPreferences("peakpace_prefs", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "") ?: ""
        val apiToken = prefs.getString("api_token", "")
        val excluded = prefs.getStringSet("excluded_origins", emptySet()) ?: emptySet()

        if (serverUrl.isBlank()) {
            Log.w(TAG, "No server URL configured; nothing to do.")
            return@withContext Result.failure()
        }

        val healthManager = HealthConnectManager(applicationContext)
        val status = healthManager.permissionStatus()

        // Only the core data permissions are required. Previously this demanded
        // every permission including the optional extras, so a single denied
        // toggle left the worker retrying forever without ever syncing.
        if (!status.core) {
            Log.w(TAG, "Core permissions missing: ${status.missing}")
            return@withContext Result.retry()
        }
        if (!status.background) {
            // Reads from a background worker fail without this, so retrying is
            // pointless until the user grants it in Health Connect settings.
            Log.w(TAG, "Background read permission not granted; skipping this run.")
            return@withContext Result.success()
        }

        val apiClient = SyncApiClient(serverUrl, apiToken)

        try {
            var synced = 0
            var failed = 0
            for (session in healthManager.fetchRunningSessions(daysBack = 7, excludedPackages = excluded)) {
                val res = apiClient.syncWorkoutSession(session)
                if (res.isSuccess) synced++ else {
                    failed++
                    Log.w(TAG, "Session sync failed: ${res.exceptionOrNull()?.message}")
                }
            }
            for (day in healthManager.fetchDailyWellness(daysBack = 7)) {
                apiClient.syncDailyWellness(day)
            }
            Log.d(TAG, "Background sync complete: $synced sent, $failed failed.")
            if (synced == 0 && failed > 0) Result.retry() else Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Background sync error: ${e.message}", e)
            Result.retry()
        }
    }

    companion object {
        private const val TAG = "PeakPace"
    }
}
