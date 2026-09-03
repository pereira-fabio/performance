package com.performance.app.ui

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.*
import com.performance.app.data.HealthConnectManager
import com.performance.app.data.PermissionStatus
import com.performance.app.data.WorkoutSessionData
import com.performance.app.worker.SyncWorker
import com.performance.app.data.SyncApiClient
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

@Composable
private fun SectionLabel(text: String) {
    Text(
        text.uppercase(),
        fontSize = 11.sp,
        fontWeight = FontWeight.Medium,
        letterSpacing = 0.8.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 4.dp, bottom = 8.dp, top = 20.dp)
    )
}

@Composable
private fun Card(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
            .padding(16.dp),
        content = content
    )
}

@Composable
private fun PermissionLine(granted: Boolean, label: String, consequence: String) {
    Row(Modifier.padding(vertical = 6.dp)) {
        Text(
            if (granted) "●" else "○",
            color = if (granted) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 13.sp,
            modifier = Modifier.width(22.dp)
        )
        Column {
            Text(label, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            if (!granted) {
                Text(consequence, fontSize = 12.sp,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    healthConnectManager: HealthConnectManager,
    permissionEpoch: Int,
    onRequestPermissions: () -> Unit,
    onClose: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("peakpace_prefs", Context.MODE_PRIVATE) }

    var serverUrl by remember { mutableStateOf(prefs.getString("server_url", "http://192.168.178.160:8000") ?: "") }
    var apiToken by remember { mutableStateOf(prefs.getString("api_token", "") ?: "") }
    var autoSync by remember { mutableStateOf(prefs.getBoolean("auto_sync", true)) }
    var excluded by remember {
        mutableStateOf(prefs.getStringSet("excluded_origins", emptySet())?.toSet() ?: emptySet())
    }

    var status by remember { mutableStateOf<PermissionStatus?>(null) }
    var origins by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var sessions by remember { mutableStateOf<List<WorkoutSessionData>>(emptyList()) }
    var syncing by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(permissionEpoch, excluded) {
        val s = healthConnectManager.permissionStatus()
        status = s
        if (s.core) {
            origins = healthConnectManager.discoverSessionOrigins(365)
            sessions = healthConnectManager.fetchRunningSessions(365, excluded)
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text("Settings", fontSize = 17.sp, fontWeight = FontWeight.SemiBold) },
                navigationIcon = {
                    TextButton(onClick = onClose) { Text("Back") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp)
        ) {
            SectionLabel("Server")
            Card {
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it; prefs.edit().putString("server_url", it).apply() },
                    label = { Text("Address") },
                    placeholder = { Text("http://192.168.178.160:8000") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                    shape = RoundedCornerShape(10.dp)
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = apiToken,
                    onValueChange = { apiToken = it; prefs.edit().putString("api_token", it).apply() },
                    label = { Text("Sync token") },
                    supportingText = { Text("Leave empty unless the server requires one") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                    shape = RoundedCornerShape(10.dp)
                )
            }

            SectionLabel("Health Connect")
            Card {
                val s = status
                if (s == null) {
                    Text("Checking…", fontSize = 14.sp,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    PermissionLine(s.core, "Workout & health data",
                        "Required — nothing can be read without this.")
                    PermissionLine(s.routes, "Exercise routes",
                        "Without this there is no GPS, so no pace or distance.")
                    PermissionLine(s.history, "Access past data",
                        "Without this only the last 30 days can be read.")
                    PermissionLine(s.background, "Background access",
                        "Without this the automatic sync cannot read anything.")

                    Spacer(Modifier.height(12.dp))
                    Text(
                        if (s.missing.isEmpty())
                            "All granted. Routes, past data and background access can be " +
                                "changed at any time under Additional access in Health Connect."
                        else
                            "Routes, past data and background access are granted separately, " +
                                "under Additional access in Health Connect.",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(12.dp))
                    // Always offered: permissions are worth reviewing and
                    // revoking, not only granting, so hiding this once
                    // everything was allowed left no way back in.
                    Button(
                        onClick = onRequestPermissions,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = if (s.missing.isEmpty())
                            ButtonDefaults.outlinedButtonColors(
                                contentColor = MaterialTheme.colorScheme.onSurface
                            ) else ButtonDefaults.buttonColors()
                    ) {
                        Text(
                            when {
                                !s.core -> "Grant permissions"
                                s.missing.isEmpty() -> "Review permissions"
                                else -> "Grant remaining permissions"
                            }
                        )
                    }
                }
            }

            if (origins.isNotEmpty()) {
                SectionLabel("Data sources")
                Card {
                    Text(
                        "More than one app can publish the same workout. Turn off any source " +
                            "that only mirrors another.",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(6.dp))
                    origins.entries.sortedByDescending { it.value }.forEach { (pkg, count) ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(pkg.substringAfterLast('.').replaceFirstChar { it.uppercase() },
                                     fontSize = 14.sp, fontWeight = FontWeight.Medium)
                                Text("$count session(s)", fontSize = 11.sp,
                                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(checked = pkg !in excluded, onCheckedChange = { on ->
                                excluded = if (on) excluded - pkg else excluded + pkg
                                prefs.edit().putStringSet("excluded_origins", excluded).apply()
                            })
                        }
                    }
                }
            }

            SectionLabel("Sync")
            Card {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Automatic", fontSize = 14.sp, fontWeight = FontWeight.Medium)
                        Text(
                            if (status?.background == false) "Needs background access, above"
                            else "Every hour, on a network connection",
                            fontSize = 12.sp,
                            color = if (status?.background == false) MaterialTheme.colorScheme.error
                                    else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Switch(checked = autoSync, onCheckedChange = { on ->
                        autoSync = on
                        prefs.edit().putBoolean("auto_sync", on).apply()
                        val wm = WorkManager.getInstance(context)
                        if (on) {
                            wm.enqueueUniquePeriodicWork(
                                "peakpace_sync_worker", ExistingPeriodicWorkPolicy.UPDATE,
                                PeriodicWorkRequestBuilder<SyncWorker>(1, TimeUnit.HOURS)
                                    .setConstraints(Constraints.Builder()
                                        .setRequiredNetworkType(NetworkType.CONNECTED).build())
                                    .build()
                            )
                        } else wm.cancelUniqueWork("peakpace_sync_worker")
                    })
                }

                Spacer(Modifier.height(14.dp))
                Button(
                    onClick = {
                        syncing = true
                        message = "Reading Health Connect…"
                        scope.launch {
                            try {
                                val api = SyncApiClient(serverUrl, apiToken)
                                val found = healthConnectManager.fetchRunningSessions(365, excluded)
                                sessions = found
                                if (found.isEmpty()) {
                                    message = "No workouts found."
                                } else {
                                    var ok = 0
                                    var lastError: String? = null
                                    found.forEach {
                                        val r = api.syncWorkoutSession(it)
                                        if (r.isSuccess) ok++ else lastError = r.exceptionOrNull()?.message
                                    }
                                    healthConnectManager.fetchDailyWellness(30)
                                        .forEach { api.syncDailyWellness(it) }
                                    message = if (ok == 0 && lastError != null) "Sync failed: $lastError"
                                              else "Synced $ok of ${found.size} workouts"
                                }
                            } catch (e: Exception) {
                                message = "Sync error: ${e.message}"
                            } finally {
                                syncing = false
                            }
                        }
                    },
                    enabled = !syncing && serverUrl.isNotBlank() && status?.core == true,
                    modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)
                ) {
                    if (syncing) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp,
                                                  color = MaterialTheme.colorScheme.onPrimary)
                        Spacer(Modifier.width(10.dp))
                        Text("Syncing…")
                    } else Text("Sync now")
                }

                message?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, fontSize = 12.sp,
                         color = if (it.contains("fail", true) || it.contains("error", true))
                             MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                }
            }

            if (sessions.isNotEmpty()) {
                SectionLabel("Detected")
                Card {
                    sessions.groupingBy { it.sportType }.eachCount().entries
                        .sortedByDescending { it.value }.forEach { (sport, n) ->
                            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp),
                                horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(sport.replaceFirstChar { it.uppercase() }, fontSize = 14.sp)
                                Text("$n", fontSize = 14.sp, fontWeight = FontWeight.Medium,
                                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                }
            }
        }
    }
}
