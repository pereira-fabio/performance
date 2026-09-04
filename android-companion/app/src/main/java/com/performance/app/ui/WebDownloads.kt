package com.performance.app.ui

import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.core.content.FileProvider
import java.io.File

/**
 * Saving a file the dashboard produced.
 *
 * The dashboard builds its downloads in the browser -- it fetches the PDF with
 * the session header, wraps it in a blob and clicks a link -- which a plain
 * WebView drops on the floor: a DownloadListener fires, but DownloadManager
 * cannot fetch a blob: URL and there is no session on a bare request anyway.
 *
 * So the blob is read back out of the page as base64 and written here. It is a
 * detour, but the alternative is putting the session token in a URL, and a
 * token in a URL ends up in logs.
 */
const val DOWNLOAD_BRIDGE = "AndroidDownloads"

class DownloadBridge(
    private val context: Context,
    onResult: (String) -> Unit,
) {
    // Methods on a JavascriptInterface run on the WebView's own JavaScript
    // thread, not the main one, so the result is posted rather than written
    // straight into Compose state from whichever thread happens to call in.
    private val main = Handler(Looper.getMainLooper())
    private val report: (String) -> Unit = { message -> main.post { onResult(message) } }

    /** Called from the page with the file's bytes, once it has read its blob. */
    @JavascriptInterface
    fun save(base64: String, mimeType: String, fileName: String) {
        if (base64.isBlank()) {
            // The page's own failure path calls in with nothing rather than
            // leaving the download hanging. Saving an empty file would be worse
            // than saying so.
            report("The dashboard could not produce that file.")
            return
        }
        val bytes = try {
            // The page sends a data: URL; only the part after the comma is data.
            Base64.decode(base64.substringAfter(","), Base64.DEFAULT)
        } catch (e: IllegalArgumentException) {
            report("Could not read the file the dashboard produced.")
            return
        }
        val name = fileName.ifBlank { "download" }
        try {
            val uri = write(bytes, name, mimeType)
            report("Saved $name")
            open(uri, mimeType)
        } catch (e: Exception) {
            report("Could not save $name: ${e.message}")
        }
    }

    private fun write(bytes: ByteArray, name: String, mimeType: String): Uri {
        // From Android 10 the Downloads collection is writable without any
        // permission at all; before that it is not, so the app's own external
        // directory is used instead -- still readable by a file manager, and
        // still openable by the viewer intent below.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mimeType.ifBlank { "application/octet-stream" })
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("the Downloads folder refused the file")
            resolver.openOutputStream(uri).use { out ->
                out?.write(bytes) ?: throw IllegalStateException("could not open the file")
            }
            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            return uri
        }

        val dir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
            ?: throw IllegalStateException("no storage available")
        dir.mkdirs()
        val file = File(dir, name)
        file.writeBytes(bytes)
        return FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    }

    /** Offer to open it. A saved file nobody can find has not really arrived. */
    private fun open(uri: Uri, mimeType: String) {
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mimeType.ifBlank { "application/octet-stream" })
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            // Nothing installed that opens a PDF. It is saved either way.
        }
    }
}

/**
 * Hand a download the page started back to the page, as base64.
 *
 * Reading the blob has to happen in the page's own context, because that is
 * the only place the blob exists.
 */
private fun readBlobScript(url: String, mimeType: String, fileName: String): String = """
    (function() {
      fetch(${quoteJs(url)})
        .then(function(r) { return r.blob(); })
        .then(function(b) {
          var reader = new FileReader();
          reader.onloadend = function() {
            $DOWNLOAD_BRIDGE.save(reader.result, ${quoteJs(mimeType)}, ${quoteJs(fileName)});
          };
          reader.readAsDataURL(b);
        })
        .catch(function(e) {
          $DOWNLOAD_BRIDGE.save('', ${quoteJs(mimeType)}, '');
        });
    })();
""".trimIndent()

private fun quoteJs(value: String): String =
    "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "") + "\""

/** Wire up downloads for a WebView showing the dashboard. */
fun WebView.enableDownloads(context: Context, onResult: (String) -> Unit) {
    addJavascriptInterface(DownloadBridge(context, onResult), DOWNLOAD_BRIDGE)
    setDownloadListener { url, _, contentDisposition, mimeType, _ ->
        val name = fileNameFrom(contentDisposition, mimeType)
        if (url.startsWith("blob:")) {
            evaluateJavascript(readBlobScript(url, mimeType, name), null)
        } else {
            // A plain URL the page linked to directly: hand it to the system.
            try {
                context.startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            } catch (e: ActivityNotFoundException) {
                onResult("Nothing on this phone can open that file.")
            }
        }
    }
}

private fun fileNameFrom(contentDisposition: String?, mimeType: String): String {
    // The header is `attachment; filename="x.pdf"; filename*=UTF-8''x.pdf`, so
    // the value has to be cut at the next parameter before it is unquoted --
    // trimming the ends of the whole tail leaves filename* stuck to the name.
    val fromHeader = contentDisposition
        ?.substringAfter("filename=", "")
        ?.substringBefore(';')
        ?.trim('"', ' ')
        ?.takeIf { it.isNotBlank() && !it.contains('/') }
    if (fromHeader != null) return fromHeader
    val extension = when {
        mimeType.contains("pdf") -> "pdf"
        mimeType.contains("json") -> "json"
        else -> "bin"
    }
    return "performance-${System.currentTimeMillis()}.$extension"
}
