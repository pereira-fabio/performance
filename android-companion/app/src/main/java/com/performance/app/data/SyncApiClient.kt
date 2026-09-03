package com.performance.app.data

import com.google.gson.FieldNamingPolicy
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/** Result of signing in: the session token and who it belongs to. */
data class SignInResult(val token: String, val username: String, val displayName: String?)

class SyncApiClient(
    private val baseUrl: String,
    private val apiToken: String? = null
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val gson: Gson = GsonBuilder()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    /**
     * Exchange a username and password for a session token.
     *
     * The phone holds a token rather than the password, so revoking access
     * server-side is enough and the password is never stored on the device.
     */
    suspend fun signIn(username: String, password: String): Result<SignInResult> =
        withContext(Dispatchers.IO) {
            try {
                val body = gson.toJson(mapOf("username" to username, "password" to password))
                val request = Request.Builder()
                    .url("${baseUrl.trimEnd('/')}/api/v1/auth/login")
                    .post(body.toRequestBody(jsonMediaType))
                    .build()
                client.newCall(request).execute().use { response ->
                    val text = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        val detail = runCatching {
                            gson.fromJson(text, Map::class.java)["detail"] as? String
                        }.getOrNull()
                        return@withContext Result.failure(
                            Exception(detail ?: "Sign-in failed (HTTP ${response.code})")
                        )
                    }
                    @Suppress("UNCHECKED_CAST")
                    val map = gson.fromJson(text, Map::class.java) as Map<String, Any?>
                    Result.success(
                        SignInResult(
                            token = map["token"] as String,
                            username = map["username"] as String,
                            displayName = map["display_name"] as? String,
                        )
                    )
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun syncWorkoutSession(session: WorkoutSessionData): Result<String> = withContext(Dispatchers.IO) {
        try {
            val jsonPayload = gson.toJson(session)
            val requestBuilder = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/v1/sync/session")
                .post(jsonPayload.toRequestBody(jsonMediaType))

            if (!apiToken.isNullOrBlank()) {
                requestBuilder.addHeader("Authorization", "Bearer $apiToken")
            }

            val response = client.newCall(requestBuilder.build()).execute()
            if (response.isSuccessful) {
                Result.success(response.body?.string() ?: "OK")
            } else if (response.code == 401) {
                Result.failure(Exception("Not signed in — open Settings and sign in again"))
            } else {
                Result.failure(Exception("Server returned HTTP ${response.code}: ${response.message}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun syncDailyWellness(wellness: DailyWellnessData): Result<String> = withContext(Dispatchers.IO) {
        try {
            val jsonPayload = gson.toJson(wellness)
            val requestBuilder = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/v1/sync/daily-health")
                .post(jsonPayload.toRequestBody(jsonMediaType))

            if (!apiToken.isNullOrBlank()) {
                requestBuilder.addHeader("Authorization", "Bearer $apiToken")
            }

            val response = client.newCall(requestBuilder.build()).execute()
            if (response.isSuccessful) {
                Result.success(response.body?.string() ?: "OK")
            } else {
                Result.failure(Exception("Server returned HTTP ${response.code}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
