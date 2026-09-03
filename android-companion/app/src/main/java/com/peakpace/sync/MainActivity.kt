package com.peakpace.sync

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.mutableIntStateOf
import androidx.health.connect.client.PermissionController
import com.peakpace.sync.data.HealthConnectManager
import com.peakpace.sync.ui.MainScreen

class MainActivity : ComponentActivity() {

    private lateinit var healthConnectManager: HealthConnectManager

    // Bumping this makes MainScreen re-read permission state. The previous
    // build called setContent() again from the permission callback, which
    // built a second composition on top of the first.
    private val permissionEpoch = mutableIntStateOf(0)

    private val requestPermissionsLauncher = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) {
        permissionEpoch.intValue += 1
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthConnectManager = HealthConnectManager(this)

        setContent {
            MainScreen(
                healthConnectManager = healthConnectManager,
                permissionEpoch = permissionEpoch.intValue,
                onRequestPermissions = { requestPermissions() }
            )
        }
    }

    override fun onResume() {
        super.onResume()
        // The user may have granted "Additional access" in Health Connect's own
        // settings while this activity was backgrounded.
        permissionEpoch.intValue += 1
    }

    private fun requestPermissions() {
        requestPermissionsLauncher.launch(healthConnectManager.permissions)
    }
}
