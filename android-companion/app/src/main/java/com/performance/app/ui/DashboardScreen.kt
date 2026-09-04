package com.performance.app.ui

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import java.net.URLEncoder

/** The dashboard ships inside the app; only data comes from the server. */
private const val LOCAL_DASHBOARD = "file:///android_asset/www/index.html"

/**
 * Build the API base the bundled dashboard should call.
 *
 * The page itself is local, so it has no origin to be relative to and must be
 * told where the API lives. The sync address already points at it.
 */
fun apiBaseFor(serverUrl: String): String {
    val base = serverUrl.trim().trimEnd('/')
    if (base.isEmpty()) return ""
    return "$base/api/v1"
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DashboardScreen(serverUrl: String, fragment: String? = null) {
    val apiBase = remember(serverUrl) { apiBaseFor(serverUrl) }
    var webView by remember { mutableStateOf<WebView?>(null) }
    var loading by remember { mutableStateOf(true) }
    var failure by remember { mutableStateOf<String?>(null) }
    var saved by remember { mutableStateOf<String?>(null) }

    BackHandler(enabled = webView?.canGoBack() == true) { webView?.goBack() }

    if (apiBase.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(
                "Set your server address on the Sync tab first.",
                fontSize = 14.sp, textAlign = TextAlign.Center,
                modifier = Modifier.padding(32.dp)
            )
        }
        return
    }

    // The fragment carries both the API base and, when the menu asks for it,
    // which screen to open -- so the web dashboard stays the single
    // implementation of the profile editor.
    val url = remember(apiBase, fragment) {
        val base = "$LOCAL_DASHBOARD#api=" + URLEncoder.encode(apiBase, "UTF-8")
        if (fragment.isNullOrBlank()) base else "$base&view=$fragment"
    }

    LaunchedEffect(url) {
        webView?.let { if (it.url != url) it.loadUrl(url) }
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
                    // The page is our own bundled asset, and it has to reach the
                    // API on the local network. Without this a file:// page is
                    // barred from making those requests.
                    settings.allowFileAccess = true
                    @Suppress("DEPRECATION")
                    settings.allowUniversalAccessFromFileURLs = true
                    settings.loadWithOverviewMode = true
                    settings.useWideViewPort = true

                    // The dashboard builds its PDF and JSON downloads as
                    // blobs, which a WebView otherwise silently discards.
                    enableDownloads(ctx) { message -> saved = message }

                    webViewClient = object : WebViewClient() {
                        override fun onPageFinished(view: WebView?, u: String?) { loading = false }

                        /**
                         * Keep this WebView on the bundled dashboard.
                         *
                         * It carries a JavaScript bridge that writes files, so
                         * only our own page may ever run in it. A link to
                         * anywhere else opens in the real browser, which is
                         * also where the reader would rather it opened.
                         */
                        override fun shouldOverrideUrlLoading(
                            view: WebView?, request: WebResourceRequest?
                        ): Boolean {
                            val target = request?.url ?: return false
                            if (target.toString().startsWith("file:///android_asset/")) {
                                return false
                            }
                            try {
                                ctx.startActivity(
                                    Intent(Intent.ACTION_VIEW, target)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                            } catch (e: ActivityNotFoundException) {
                                // No browser installed; refusing is still right.
                            }
                            return true
                        }
                        override fun onReceivedError(
                            view: WebView?, request: WebResourceRequest?, error: WebResourceError?
                        ) {
                            if (request?.isForMainFrame == true) {
                                loading = false
                                failure = "Could not load the dashboard."
                            }
                        }
                    }
                    webView = this
                    loadUrl(url)
                }
            }
        )

        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter))

        // A download is invisible otherwise: the file lands in Downloads with
        // nothing on screen to say it worked.
        saved?.let { message ->
            LaunchedEffect(message) {
                kotlinx.coroutines.delay(4000)
                saved = null
            }
            Snackbar(
                modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp)
            ) { Text(message, fontSize = 13.sp) }
        }

        failure?.let { message ->
            Surface(
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
                shape = MaterialTheme.shapes.medium, tonalElevation = 2.dp
            ) {
                Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(message, fontSize = 14.sp, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = {
                        failure = null; loading = true; webView?.loadUrl(url)
                    }) { Text("Retry") }
                }
            }
        }
    }
}
