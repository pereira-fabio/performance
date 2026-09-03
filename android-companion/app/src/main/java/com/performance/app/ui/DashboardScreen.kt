package com.performance.app.ui

import android.annotation.SuppressLint
import android.content.Context
import android.view.ViewGroup
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Derive the dashboard address from the sync address.
 *
 * The API and the web front end are separate services on separate ports, so a
 * single URL cannot serve both. Rather than making the user configure two, the
 * common Docker layout (API on 8000, dashboard on 3000) is assumed and can be
 * overridden when it does not hold.
 */
fun deriveDashboardUrl(serverUrl: String, override: String?): String {
    if (!override.isNullOrBlank()) return override.trim()
    val base = serverUrl.trim().trimEnd('/')
    if (base.isEmpty()) return ""
    return if (base.endsWith(":8000")) base.removeSuffix(":8000") + ":3000" else base
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DashboardScreen(serverUrl: String, dashboardOverride: String?) {
    val context = LocalContext.current
    val url = remember(serverUrl, dashboardOverride) { deriveDashboardUrl(serverUrl, dashboardOverride) }

    var webView by remember { mutableStateOf<WebView?>(null) }
    var loading by remember { mutableStateOf(true) }
    var failure by remember { mutableStateOf<String?>(null) }
    var reloadKey by remember { mutableIntStateOf(0) }

    // Inside the dashboard, Back should navigate the page, not leave the app.
    BackHandler(enabled = webView?.canGoBack() == true) { webView?.goBack() }

    if (url.isBlank()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(
                "Set your server address on the Sync tab first.",
                fontSize = 14.sp, textAlign = TextAlign.Center,
                modifier = Modifier.padding(32.dp)
            )
        }
        return
    }

    Box(Modifier.fillMaxSize()) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx: Context ->
                WebView(ctx).apply {
                    layoutParams = ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
                    )
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.loadWithOverviewMode = true
                    settings.useWideViewPort = true
                    webViewClient = object : WebViewClient() {
                        override fun onPageFinished(view: WebView?, u: String?) { loading = false }
                        override fun onReceivedError(
                            view: WebView?, request: WebResourceRequest?, error: WebResourceError?
                        ) {
                            // Only the main document failing is worth reporting;
                            // a missing sub-resource should not blank the screen.
                            if (request?.isForMainFrame == true) {
                                loading = false
                                failure = "Could not reach $url"
                            }
                        }
                    }
                    webView = this
                    loadUrl(url)
                }
            },
            update = { view ->
                if (reloadKey > 0) {
                    view.tag?.let { }
                }
            }
        )

        if (loading) {
            LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter))
        }

        failure?.let { message ->
            Surface(
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
                shape = MaterialTheme.shapes.medium,
                tonalElevation = 2.dp
            ) {
                Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(message, fontSize = 14.sp, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Check the address on the Sync tab and that the server is running.",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center
                    )
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = {
                        failure = null
                        loading = true
                        reloadKey++
                        webView?.loadUrl(url)
                    }) { Text("Retry") }
                }
            }
        }
    }
}
