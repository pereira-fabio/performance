package com.peakpace.sync.data

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
