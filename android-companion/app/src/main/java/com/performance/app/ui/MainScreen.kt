package com.performance.app.ui

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.*
import com.performance.app.data.HealthConnectManager
import com.performance.app.data.PermissionStatus
import com.performance.app.data.SyncApiClient
import com.performance.app.data.WorkoutSessionData
import com.performance.app.worker.SyncWorker
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

private val OK_GREEN = Color(0xFF10B981)
private val WARN_AMBER = Color(0xFFF59E0B)

@Composable
private fun PermissionRow(granted: Boolean, label: String, consequence: String) {
    Row(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(
            text = if (granted) "✓" else "!",
            color = if (granted) OK_GREEN else WARN_AMBER,
            fontWeight = FontWeight.Bold,
            fontSize = 14.sp,
            modifier = Modifier.width(20.dp)
        )
        Column {
            Text(label, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            if (!granted) {
                Text(consequence, fontSize = 11.sp, color = Color.Gray)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncScreen(
    healthConnectManager: HealthConnectManager,
    permissionEpoch: Int = 0,
    onRequestPermissions: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("peakpace_prefs", Context.MODE_PRIVATE) }

    var serverUrl by remember { mutableStateOf(prefs.getString("server_url", "http://192.168.1.100:8000") ?: "") }
    var apiToken by remember { mutableStateOf(prefs.getString("api_token", "") ?: "") }
    var autoSyncEnabled by remember { mutableStateOf(prefs.getBoolean("auto_sync", true)) }
    var dashboardUrl by remember { mutableStateOf(prefs.getString("dashboard_url", "") ?: "") }

    var status by remember { mutableStateOf<PermissionStatus?>(null) }
    var isSyncing by remember { mutableStateOf(false) }
    var syncStatusMessage by remember { mutableStateOf<String?>(null) }
    var sessionsList by remember { mutableStateOf<List<WorkoutSessionData>>(emptyList()) }
    var origins by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var excluded by remember {
        mutableStateOf(prefs.getStringSet("excluded_origins", emptySet())?.toSet() ?: emptySet())
    }

    // Re-read whenever the user returns from a Health Connect permission screen.
    LaunchedEffect(permissionEpoch, excluded) {
        val s = healthConnectManager.permissionStatus()
        status = s
        if (s.core) {
            origins = healthConnectManager.discoverSessionOrigins(daysBack = 365)
            sessionsList = healthConnectManager.fetchRunningSessions(
                daysBack = 365, excludedPackages = excluded
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("PeakPace Sync", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text("Health Connect to Home Server", fontSize = 12.sp, color = Color.Gray)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Server Endpoint", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedTextField(
                            value = serverUrl,
                            onValueChange = {
                                serverUrl = it
                                prefs.edit().putString("server_url", it).apply()
                            },
                            label = { Text("Server Base URL") },
                            placeholder = { Text("http://192.168.1.150:8000") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedTextField(
                            value = apiToken,
                            onValueChange = {
                                apiToken = it
                                prefs.edit().putString("api_token", it).apply()
                            },
                            label = { Text("API Sync Token (Optional)") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        // The dashboard is a separate service from the API, so
                        // it has its own address. Left blank, it is derived by
                        // swapping the API port for the web one.
                        OutlinedTextField(
                            value = dashboardUrl,
                            onValueChange = {
                                dashboardUrl = it
                                prefs.edit().putString("dashboard_url", it).apply()
                            },
                            label = { Text("Dashboard URL (optional)") },
                            placeholder = { Text(deriveDashboardUrl(serverUrl, null)) },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )
                    }
                }
            }

            item {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Health Connect Access", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Spacer(modifier = Modifier.height(8.dp))

                        val s = status
                        if (s == null) {
                            Text("Checking…", fontSize = 13.sp, color = Color.Gray)
                        } else {
                            PermissionRow(
                                s.core, "Workout & health data",
                                "Required. Nothing can be read without this."
                            )
                            PermissionRow(
                                s.routes, "Exercise routes (GPS)",
                                "Without this there is no GPS track, so no pace, distance or grade."
                            )
                            PermissionRow(
                                s.history, "Access past data",
                                "Without this only the last 30 days can be read, so older runs never sync."
                            )
                            PermissionRow(
                                s.background, "Access data in the background",
                                "Without this the hourly automatic sync cannot read anything."
                            )

                            if (s.missing.isNotEmpty()) {
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(
                                    "Routes, past data and background access are granted separately " +
                                        "in Health Connect → App permissions → PeakPace Sync → " +
                                        "Additional access.",
                                    fontSize = 11.sp,
                                    color = Color.Gray
                                )
                                Spacer(modifier = Modifier.height(10.dp))
                                Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth()) {
                                    Text(if (s.core) "Grant Remaining Permissions" else "Grant Health Connect Permissions")
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                isSyncing = true
                                syncStatusMessage = "Reading Health Connect workouts…"
                                coroutineScope.launch {
                                    try {
                                        val apiClient = SyncApiClient(serverUrl, apiToken)
                                        val sessions = healthConnectManager.fetchRunningSessions(
                                            daysBack = 365, excludedPackages = excluded
                                        )
                                        sessionsList = sessions

                                        if (sessions.isEmpty()) {
                                            syncStatusMessage = "No workouts found. Check that your " +
                                                "watch app has permission to write to Health Connect."
                                            isSyncing = false
                                            return@launch
                                        }

                                        var synced = 0
                                        var lastError: String? = null
                                        for (session in sessions) {
                                            val res = apiClient.syncWorkoutSession(session)
                                            if (res.isSuccess) synced++
                                            else lastError = res.exceptionOrNull()?.message
                                        }
                                        for (day in healthConnectManager.fetchDailyWellness(daysBack = 30)) {
                                            apiClient.syncDailyWellness(day)
                                        }

                                        syncStatusMessage = if (lastError != null && synced == 0) {
                                            "Sync failed: $lastError"
                                        } else {
                                            "✓ Synced $synced of ${sessions.size} workout(s)" +
                                                (lastError?.let { " — last error: $it" } ?: "")
                                        }
                                    } catch (e: Exception) {
                                        syncStatusMessage = "Sync error: ${e.message}"
                                    } finally {
                                        isSyncing = false
                                    }
                                }
                            },
                            enabled = !isSyncing && serverUrl.isNotBlank() && (status?.core == true),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            if (isSyncing) {
                                CircularProgressIndicator(modifier = Modifier.size(18.dp), color = Color.White)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Syncing…")
                            } else {
                                Text("Sync Now")
                            }
                        }

                        syncStatusMessage?.let { msg ->
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = msg,
                                fontSize = 12.sp,
                                color = if (msg.contains("fail", ignoreCase = true) ||
                                    msg.contains("error", ignoreCase = true)
                                ) MaterialTheme.colorScheme.error else OK_GREEN
                            )
                        }
                    }
                }
            }

            if (origins.isNotEmpty()) {
                item {
                    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Data Sources", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            Text(
                                "More than one app can publish the same workout. Turn off any " +
                                    "source that only mirrors another, so its copies are ignored.",
                                fontSize = 11.sp,
                                color = Color.Gray
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            origins.entries.sortedByDescending { it.value }.forEach { (pkg, count) ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            pkg.substringAfterLast('.')
                                                .replaceFirstChar { it.uppercase() },
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.SemiBold
                                        )
                                        Text("$pkg · $count session(s)", fontSize = 10.sp, color = Color.Gray)
                                    }
                                    Switch(
                                        checked = pkg !in excluded,
                                        onCheckedChange = { enabled ->
                                            excluded = if (enabled) excluded - pkg else excluded + pkg
                                            prefs.edit()
                                                .putStringSet("excluded_origins", excluded)
                                                .apply()
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Hourly Background Sync", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(
                            if (status?.background == false)
                                "Needs background access, granted above"
                            else "Syncs automatically via WorkManager",
                            fontSize = 12.sp,
                            color = if (status?.background == false) WARN_AMBER else Color.Gray
                        )
                    }
                    Switch(
                        checked = autoSyncEnabled,
                        onCheckedChange = { checked ->
                            autoSyncEnabled = checked
                            prefs.edit().putBoolean("auto_sync", checked).apply()
                            val workManager = WorkManager.getInstance(context)
                            if (checked) {
                                workManager.enqueueUniquePeriodicWork(
                                    "peakpace_sync_worker",
                                    ExistingPeriodicWorkPolicy.UPDATE,
                                    PeriodicWorkRequestBuilder<SyncWorker>(1, TimeUnit.HOURS)
                                        .setConstraints(
                                            Constraints.Builder()
                                                .setRequiredNetworkType(NetworkType.CONNECTED)
                                                .build()
                                        ).build()
                                )
                            } else {
                                workManager.cancelUniqueWork("peakpace_sync_worker")
                            }
                        }
                    )
                }
            }

            item {
                val bySport = sessionsList.groupingBy { it.sportType }.eachCount()
                Column {
                    Text(
                        "Workouts Health Connect will sync (${sessionsList.size})",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                    if (bySport.isNotEmpty()) {
                        Text(
                            bySport.entries.joinToString(", ") { "${it.value} ${it.key}" },
                            fontSize = 11.sp,
                            color = Color.Gray
                        )
                    }
                }
            }

            items(sessionsList) { session ->
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(session.title, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text(
                                String.format("%.2f km", (session.distanceMeters ?: 0.0) / 1000.0),
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "${session.startTime.take(19).replace("T", " ")} · " +
                                "${session.sportType} · ${session.heartRateSeries.size} HR · " +
                                "${session.routePoints.size} GPS",
                            fontSize = 11.sp,
                            color = Color.Gray
                        )
                    }
                }
            }
        }
    }
}
