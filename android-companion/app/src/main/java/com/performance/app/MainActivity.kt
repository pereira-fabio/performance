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
    var menuOpen by rememberSaveable { mutableStateOf(false) }
    // A fragment on the dashboard URL, so opening the profile reuses the web
    // screen rather than reimplementing the same editor natively.
    var dashboardFragment by rememberSaveable { mutableStateOf<String?>(null) }
    val serverUrl = prefs.getString("server_url", "") ?: ""

    BackHandler(enabled = settingsOpen || menuOpen) {
        if (settingsOpen) settingsOpen = false else menuOpen = false
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // The dashboard is the app. It carries its own header, so the only
        // chrome around it is a single way into settings.
        Column(Modifier.fillMaxSize()) {
            MenuStrip(onOpen = { menuOpen = true })
            DashboardScreen(serverUrl, dashboardFragment)
        }

        if (menuOpen) {
            AppMenu(
                onDismiss = { menuOpen = false },
                onProfile = {
                    menuOpen = false
                    // Cache-busted so re-selecting it reopens the screen.
                    dashboardFragment = "profile-" + System.currentTimeMillis()
                },
                onSettings = { menuOpen = false; settingsOpen = true },
            )
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

/** One control, top left; the dashboard below supplies the branding. */
@Composable
private fun MenuStrip(onOpen: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .height(40.dp)
            .padding(horizontal = 4.dp),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onOpen) {
            Text("\u2261", fontSize = 22.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppMenu(
    onDismiss: () -> Unit,
    onProfile: () -> Unit,
    onSettings: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss,
                     containerColor = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxWidth().padding(bottom = 28.dp)) {
            MenuRow("Profile", "Heart rate, thresholds, weight", onProfile)
            MenuRow("Settings", "Server connection, permissions, sync", onSettings)
        }
    }
}

@Composable
private fun MenuRow(title: String, subtitle: String, onClick: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 24.dp, vertical = 14.dp)
    ) {
        Text(title, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        Text(subtitle, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
