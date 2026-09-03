package com.performance.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.health.connect.client.PermissionController
import com.performance.app.data.HealthConnectManager
import com.performance.app.ui.DashboardScreen
import com.performance.app.ui.PerformanceTheme
import com.performance.app.ui.SettingsScreen

class MainActivity : ComponentActivity() {

    private lateinit var healthConnectManager: HealthConnectManager
    private val permissionEpoch = mutableIntStateOf(0)

    private val requestPermissionsLauncher = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) { permissionEpoch.intValue += 1 }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthConnectManager = HealthConnectManager(this)

        setContent {
            PerformanceTheme {
                AppRoot(
                    healthConnectManager = healthConnectManager,
                    permissionEpoch = permissionEpoch.intValue,
                    onRequestPermissions = {
                        requestPermissionsLauncher.launch(healthConnectManager.permissions)
                    }
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
private fun AppRoot(
    healthConnectManager: HealthConnectManager,
    permissionEpoch: Int,
    onRequestPermissions: () -> Unit,
) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("peakpace_prefs", Context.MODE_PRIVATE) }
    var settingsOpen by rememberSaveable { mutableStateOf(false) }
    // A fragment on the dashboard URL, so opening the profile reuses the web
    // screen rather than reimplementing the same editor natively.
    var dashboardFragment by rememberSaveable { mutableStateOf<String?>(null) }
    val serverUrl = prefs.getString("server_url", "") ?: ""

    BackHandler(enabled = settingsOpen) { settingsOpen = false }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // The dashboard is the app. It carries its own header, so the only
        // chrome around it is a single way into settings.
        Column(Modifier.fillMaxSize()) {
            ConnectionStrip(onOpen = { settingsOpen = true })
            DashboardScreen(serverUrl, dashboardFragment)
        }

        AnimatedVisibility(
            visible = settingsOpen,
            enter = slideInHorizontally { it },
            exit = slideOutHorizontally { it },
        ) {
            SettingsScreen(
                healthConnectManager = healthConnectManager,
                permissionEpoch = permissionEpoch,
                onRequestPermissions = onRequestPermissions,
                onClose = { settingsOpen = false },
            )
        }
    }
}

/**
 * The only chrome the app adds: a way into the server connection.
 *
 * Everything about the athlete lives in the dashboard below, which has its own
 * menu, so this is deliberately not a second navigation -- it is one control
 * for the one thing the dashboard cannot configure about itself.
 */
@Composable
private fun ConnectionStrip(onOpen: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .height(40.dp)
            .padding(horizontal = 4.dp),
        horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onOpen) {
            Icon(
                imageVector = Icons.Filled.Settings,
                contentDescription = "Server connection",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

