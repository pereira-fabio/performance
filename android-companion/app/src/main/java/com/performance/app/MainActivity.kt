package com.performance.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.health.connect.client.PermissionController
import com.performance.app.data.HealthConnectManager
import com.performance.app.ui.DashboardScreen
import com.performance.app.ui.SyncScreen

private enum class Destination(val label: String) {
    Dashboard("Dashboard"),
    Sync("Sync"),
}

class MainActivity : ComponentActivity() {

    private lateinit var healthConnectManager: HealthConnectManager

    // Bumped when permissions change, so the sync screen re-reads its state
    // rather than the activity rebuilding its whole content tree.
    private val permissionEpoch = mutableIntStateOf(0)

    private val requestPermissionsLauncher = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) { permissionEpoch.intValue += 1 }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthConnectManager = HealthConnectManager(this)

        setContent {
            MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme()) {
                AppScaffold(
                    healthConnectManager = healthConnectManager,
                    permissionEpoch = permissionEpoch.intValue,
                    onRequestPermissions = { requestPermissionsLauncher.launch(healthConnectManager.permissions) }
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // The user may have granted "Additional access" in Health Connect's own
        // settings while this activity was in the background.
        permissionEpoch.intValue += 1
    }
}

@Composable
private fun AppScaffold(
    healthConnectManager: HealthConnectManager,
    permissionEpoch: Int,
    onRequestPermissions: () -> Unit,
) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("peakpace_prefs", Context.MODE_PRIVATE) }
    var destination by rememberSaveable { mutableStateOf(Destination.Dashboard) }

    // Read on each recomposition so returning from Sync picks up an edited URL.
    val serverUrl = prefs.getString("server_url", "") ?: ""
    val dashboardOverride = prefs.getString("dashboard_url", "")

    Scaffold(
        bottomBar = {
            NavigationBar {
                Destination.entries.forEach { d ->
                    NavigationBarItem(
                        selected = destination == d,
                        onClick = { destination = d },
                        label = { Text(d.label) },
                        icon = {},
                        alwaysShowLabel = true
                    )
                }
            }
        }
    ) { padding ->
        Surface(Modifier.padding(padding)) {
            when (destination) {
                Destination.Dashboard -> DashboardScreen(serverUrl, dashboardOverride)
                Destination.Sync -> SyncScreen(
                    healthConnectManager = healthConnectManager,
                    permissionEpoch = permissionEpoch,
                    onRequestPermissions = onRequestPermissions
                )
            }
        }
    }
}
