package com.performance.app.data

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.aggregate.AggregateMetric
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.records.metadata.DataOrigin
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import kotlin.reflect.KClass

data class WorkoutSessionData(
    val sessionId: String,
    val title: String,
    val sportType: String,
    val startTime: String,
    val endTime: String,
    val distanceMeters: Double?,
    val durationSec: Double?,
    val caloriesKcal: Double?,
    val elevationGainM: Double?,
    val steps: Int?,
    val vo2Max: Double?,
    val routePoints: List<Map<String, Any?>>,
    val heartRateSeries: List<Map<String, Any>>,
    val speedSeries: List<Map<String, Any>>,
    val cadenceSeries: List<Map<String, Any>>,
    val notes: String?
)

data class DailyWellnessData(
    val date: String,
    val restingHr: Int?,
    val hrvRmssd: Double?,
    val sleepDurationSec: Double?,
    val sleepScore: Double?,
    val vo2Max: Double?,
    val steps: Int?
)

/** What the user has actually granted, so the UI can ask for the right thing. */
data class PermissionStatus(
    val core: Boolean,
    val routes: Boolean,
    val history: Boolean,
    val background: Boolean,
    val missing: Set<String>
)

class HealthConnectManager(private val context: Context) {

    companion object {
        private const val TAG = "PeakPace"

        /**
         * Health Connect caps a single read; without following the page token
         * a long backfill is silently truncated part-way through a session.
         */
        private const val PAGE_SIZE = 1000
        private const val MAX_RECORDS_PER_TYPE = 200_000

        /**
         * These two have no constant in connect-client 1.1.0-alpha07, so they
         * are referenced by their platform permission strings. Both are granted
         * separately by the user under "Additional access" in Health Connect.
         */
        const val PERMISSION_READ_EXERCISE_ROUTES =
            "android.permission.health.READ_EXERCISE_ROUTES"
        const val PERMISSION_READ_HEALTH_DATA_HISTORY =
            "android.permission.health.READ_HEALTH_DATA_HISTORY"

        /**
         * Every session is synced under an accurate sport name. The original
         * build mapped unrecognised types to "running", so walks and gym work
         * arrived as runs; the fix for that dropped them entirely, which lost
         * real training instead. Anything unmapped now syncs as "other" and the
         * server keeps non-running sports out of running load and records.
         */
        val SPORT_TYPE_NAMES: Map<Int, String> = mapOf(
            ExerciseSessionRecord.EXERCISE_TYPE_RUNNING to "running",
            ExerciseSessionRecord.EXERCISE_TYPE_RUNNING_TREADMILL to "treadmill",
            ExerciseSessionRecord.EXERCISE_TYPE_WALKING to "walking",
            ExerciseSessionRecord.EXERCISE_TYPE_HIKING to "hiking",
            ExerciseSessionRecord.EXERCISE_TYPE_BIKING to "cycling",
            ExerciseSessionRecord.EXERCISE_TYPE_BIKING_STATIONARY to "cycling",
            ExerciseSessionRecord.EXERCISE_TYPE_STRENGTH_TRAINING to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_WEIGHTLIFTING to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_CALISTHENICS to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_HIGH_INTENSITY_INTERVAL_TRAINING to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_BOOT_CAMP to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_ELLIPTICAL to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_STAIR_CLIMBING to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_STAIR_CLIMBING_MACHINE to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_ROWING_MACHINE to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_GYMNASTICS to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_PILATES to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_YOGA to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_STRETCHING to "gym",
            // Nothing X records its "Free training" sessions as a generic
            // workout: heart rate only, no GPS or distance. Treated as gym
            // work, which keeps it out of running load and records while still
            // counting the effort.
            ExerciseSessionRecord.EXERCISE_TYPE_OTHER_WORKOUT to "gym",
            ExerciseSessionRecord.EXERCISE_TYPE_SWIMMING_POOL to "swimming",
            ExerciseSessionRecord.EXERCISE_TYPE_SWIMMING_OPEN_WATER to "swimming",
            ExerciseSessionRecord.EXERCISE_TYPE_ROWING to "rowing"
        )
        const val DEFAULT_SPORT_NAME = "other"

        /**
         * A session shorter than this carrying no route, heart rate or speed
         * has nothing to analyse. The server rejects it with HTTP 422, so it is
         * filtered here rather than sent to collect an error.
         */
        private const val MIN_SYNCABLE_DURATION_SEC = 60L

        /** Two sessions overlapping by more than this are the same workout. */
        private const val DUPLICATE_OVERLAP_FRACTION = 0.80
    }

    val healthConnectClient: HealthConnectClient? by lazy {
        if (HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE) {
            HealthConnectClient.getOrCreate(context)
        } else {
            null
        }
    }

    /**
     * The minimum needed to produce a usable run. Anything beyond this only
     * enriches the result, so a single denied toggle must not block syncing.
     */
    val corePermissions: Set<String> = setOf(
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(SpeedRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class)
    )

    /** Requested alongside the core set; absence degrades rather than blocks. */
    val enrichmentPermissions: Set<String> = setOf(
        HealthPermission.getReadPermission(TotalCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(ElevationGainedRecord::class),
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(StepsCadenceRecord::class),
        HealthPermission.getReadPermission(Vo2MaxRecord::class),
        HealthPermission.getReadPermission(HeartRateVariabilityRmssdRecord::class),
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(RestingHeartRateRecord::class)
    )

    /**
     * Granted separately by the user. Without routes there is no GPS; without
     * history only the last 30 days are readable; without background the
     * hourly WorkManager sync cannot read anything at all.
     */
    val additionalPermissions: Set<String> = setOf(
        PERMISSION_READ_EXERCISE_ROUTES,
        PERMISSION_READ_HEALTH_DATA_HISTORY,
        HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND
    )

    val permissions: Set<String> = corePermissions + enrichmentPermissions + additionalPermissions

    suspend fun grantedPermissions(): Set<String> =
        healthConnectClient?.permissionController?.getGrantedPermissions() ?: emptySet()

    suspend fun permissionStatus(): PermissionStatus {
        val granted = grantedPermissions()
        return PermissionStatus(
            core = granted.containsAll(corePermissions),
            routes = PERMISSION_READ_EXERCISE_ROUTES in granted,
            history = PERMISSION_READ_HEALTH_DATA_HISTORY in granted,
            background = HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND in granted,
            missing = permissions - granted
        )
    }

    /** Sync only needs the core types; the extras widen what it can see. */
    suspend fun hasCorePermissions(): Boolean = grantedPermissions().containsAll(corePermissions)

    // ---------------------------------------------------------------------

    /** Read every page of a record type. */
    private suspend fun <T : Record> readAll(
        type: KClass<T>,
        filter: TimeRangeFilter,
        origins: Set<DataOrigin> = emptySet()
    ): List<T> {
        val client = healthConnectClient ?: return emptyList()
        val out = mutableListOf<T>()
        var token: String? = null
        do {
            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = type,
                    timeRangeFilter = filter,
                    dataOriginFilter = origins,
                    pageSize = PAGE_SIZE,
                    pageToken = token
                )
            )
            out += response.records
            token = response.pageToken
        } while (!token.isNullOrEmpty() && out.size < MAX_RECORDS_PER_TYPE)
        return out
    }

    /**
     * Read a time series for one session.
     *
     * Totals must stay pinned to the session's own origin, because summing a
     * value across two apps double-counts it. A *series* is different: samples
     * carry timestamps, and the server collapses duplicate timestamps when it
     * resamples, so pulling from every origin cannot double-count. Falling back
     * this way recovers sessions written by one app whose heart rate was
     * recorded by another -- otherwise they look empty and get dropped.
     */
    private suspend fun <T : Record> readSeriesWithFallback(
        type: KClass<T>,
        filter: TimeRangeFilter,
        origins: Set<DataOrigin>,
        excludedPackages: Set<String>
    ): List<T> {
        val own = readAll(type, filter, origins)
        if (own.isNotEmpty()) return own
        // Excluded sources stay excluded here too, otherwise data the user
        // rejected would return through the fallback.
        val any = readAll(type, filter, emptySet())
            .filter { it.metadata.dataOrigin.packageName !in excludedPackages }
        if (any.isNotEmpty()) {
            Log.d(TAG, "${type.simpleName}: none from session origin, using ${any.size} from other origins")
        }
        return any
    }

    private suspend fun <T : Any> aggregateOrNull(
        metric: AggregateMetric<T>,
        start: Instant,
        end: Instant,
        origins: Set<DataOrigin>
    ): T? = try {
        healthConnectClient?.aggregate(
            AggregateRequest(
                metrics = setOf(metric),
                timeRangeFilter = TimeRangeFilter.between(start, end),
                dataOriginFilter = origins
            )
        )?.get(metric)
    } catch (e: Exception) {
        Log.w(TAG, "Aggregate failed: ${e.message}")
        null
    }

    /**
     * Drop sessions that describe the same workout.
     *
     * A device app and the platform's own derived records can both publish a
     * session for one run, with different ids. Syncing both produced a real
     * activity plus a zero-distance twin, and summing distance across both
     * origins doubled the reported distance.
     */
    private fun deduplicateSessions(
        sessions: List<ExerciseSessionRecord>
    ): List<ExerciseSessionRecord> {
        val sorted = sessions.sortedBy { it.startTime }
        val kept = mutableListOf<ExerciseSessionRecord>()

        for (candidate in sorted) {
            val candidateSec = ChronoUnit.SECONDS.between(candidate.startTime, candidate.endTime)
            val clashIndex = kept.indexOfFirst { existing ->
                val overlapStart = maxOf(existing.startTime, candidate.startTime)
                val overlapEnd = minOf(existing.endTime, candidate.endTime)
                val overlapSec = ChronoUnit.SECONDS.between(overlapStart, overlapEnd)
                if (overlapSec <= 0) return@indexOfFirst false
                val existingSec = ChronoUnit.SECONDS.between(existing.startTime, existing.endTime)
                val shorter = minOf(existingSec, candidateSec).coerceAtLeast(1)
                overlapSec.toDouble() / shorter >= DUPLICATE_OVERLAP_FRACTION
            }

            if (clashIndex < 0) {
                kept += candidate
                continue
            }

            // Same workout seen twice: keep whichever carries a GPS route, and
            // fall back to the longer recording.
            val existing = kept[clashIndex]
            val existingHasRoute = existing.exerciseRouteResult is ExerciseRouteResult.Data
            val candidateHasRoute = candidate.exerciseRouteResult is ExerciseRouteResult.Data
            val existingSec = ChronoUnit.SECONDS.between(existing.startTime, existing.endTime)

            val replace = when {
                candidateHasRoute && !existingHasRoute -> true
                !candidateHasRoute && existingHasRoute -> false
                else -> candidateSec > existingSec
            }
            Log.d(
                TAG,
                "Duplicate session ${candidate.metadata.id} " +
                    "(${candidate.metadata.dataOrigin.packageName}) overlaps " +
                    "${existing.metadata.id} (${existing.metadata.dataOrigin.packageName}); " +
                    if (replace) "replacing" else "skipping"
            )
            if (replace) kept[clashIndex] = candidate
        }
        return kept
    }

    /**
     * Which apps have written exercise sessions, and how many each.
     *
     * More than one app commonly publishes the same workout -- a watch app
     * writes it, and a platform like Strava writes it back after syncing. The
     * user picks which sources to trust rather than the app guessing.
     */
    suspend fun discoverSessionOrigins(daysBack: Long = 365): Map<String, Int> {
        healthConnectClient ?: return emptyMap()
        return try {
            readAll(
                ExerciseSessionRecord::class,
                TimeRangeFilter.between(Instant.now().minus(daysBack, ChronoUnit.DAYS), Instant.now())
            ).groupingBy { it.metadata.dataOrigin.packageName }.eachCount()
        } catch (e: Exception) {
            Log.w(TAG, "Could not enumerate data origins: ${e.message}")
            emptyMap()
        }
    }

    suspend fun fetchRunningSessions(
        daysBack: Long = 365,
        excludedPackages: Set<String> = emptySet()
    ): List<WorkoutSessionData> {
        val client = healthConnectClient ?: return emptyList()
        val startTime = Instant.now().minus(daysBack, ChronoUnit.DAYS)
        val endTime = Instant.now()
        val results = mutableListOf<WorkoutSessionData>()

        try {
            val all = readAll(
                ExerciseSessionRecord::class,
                TimeRangeFilter.between(startTime, endTime)
            )
            val included = if (excludedPackages.isEmpty()) all else {
                all.filter { it.metadata.dataOrigin.packageName !in excludedPackages }
            }
            val sessions = deduplicateSessions(included)
            Log.d(
                TAG,
                "Health Connect: ${all.size} sessions, ${included.size} after source filter " +
                    "(excluding ${excludedPackages.ifEmpty { setOf("nothing") }}), " +
                    "${sessions.size} after de-duplication"
            )
            var skippedEmpty = 0

            for (record in sessions) {
                val sessionStart = record.startTime
                val sessionEnd = record.endTime
                // Everything about this session is read from the app that wrote
                // it, so a second source cannot contribute to its totals.
                val origins = setOf(DataOrigin(record.metadata.dataOrigin.packageName))

                val routePoints = mutableListOf<Map<String, Any?>>()
                try {
                    val result = record.exerciseRouteResult
                    if (result is ExerciseRouteResult.Data) {
                        for (location in result.exerciseRoute.route) {
                            routePoints.add(
                                mapOf(
                                    "time" to location.time.toString(),
                                    "lat" to location.latitude,
                                    "lng" to location.longitude,
                                    "altitude" to location.altitude?.inMeters
                                )
                            )
                        }
                    } else if (result is ExerciseRouteResult.ConsentRequired) {
                        Log.w(TAG, "Route needs consent: grant READ_EXERCISE_ROUTES")
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Could not read GPS route: ${e.message}")
                }

                val hrSeries = mutableListOf<Map<String, Any>>()
                for (hrRecord in readSeriesWithFallback(
                    HeartRateRecord::class,
                    TimeRangeFilter.between(sessionStart, sessionEnd), origins, excludedPackages
                )) {
                    for (sample in hrRecord.samples) {
                        hrSeries.add(
                            mapOf("time" to sample.time.toString(), "bpm" to sample.beatsPerMinute)
                        )
                    }
                }

                val speedSeries = mutableListOf<Map<String, Any>>()
                for (speedRecord in readSeriesWithFallback(
                    SpeedRecord::class,
                    TimeRangeFilter.between(sessionStart, sessionEnd), origins, excludedPackages
                )) {
                    for (sample in speedRecord.samples) {
                        speedSeries.add(
                            mapOf(
                                "time" to sample.time.toString(),
                                "speed_mps" to sample.speed.inMetersPerSecond
                            )
                        )
                    }
                }

                val cadenceSeries = mutableListOf<Map<String, Any>>()
                for (cadRecord in readSeriesWithFallback(
                    StepsCadenceRecord::class,
                    TimeRangeFilter.between(sessionStart, sessionEnd), origins, excludedPackages
                )) {
                    for (sample in cadRecord.samples) {
                        cadenceSeries.add(
                            mapOf("time" to sample.time.toString(), "spm" to sample.rate)
                        )
                    }
                }

                // Aggregates, not raw sums. Health Connect reconciles
                // overlapping records; summing them counted distance twice.
                // Aggregates stay origin-scoped: this is exactly where summing
                // across two apps produced double the real distance.
                val distance = aggregateOrNull(
                    DistanceRecord.DISTANCE_TOTAL, sessionStart, sessionEnd, origins
                )?.inMeters
                val elevation = aggregateOrNull(
                    ElevationGainedRecord.ELEVATION_GAINED_TOTAL, sessionStart, sessionEnd, origins
                )?.inMeters
                // Active calories, not total. Total includes basal metabolism,
                // which for a 74-minute run reads about 1800 kcal against 840
                // actually burned running -- not the figure anyone means by
                // "calories burned" for a workout. Total is the fallback for
                // devices that only write it.
                val calories = aggregateOrNull(
                    ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL, sessionStart, sessionEnd, origins
                )?.inKilocalories ?: aggregateOrNull(
                    TotalCaloriesBurnedRecord.ENERGY_TOTAL, sessionStart, sessionEnd, origins
                )?.inKilocalories

                // Steps during the session, and the VO2 max reading closest to
                // it. Both are written by the device rather than derived, so
                // they are read here rather than estimated on the server.
                val steps = aggregateOrNull(
                    StepsRecord.COUNT_TOTAL, sessionStart, sessionEnd, origins
                )?.toInt()

                val vo2 = try {
                    readAll(
                        Vo2MaxRecord::class,
                        TimeRangeFilter.between(
                            sessionStart.minus(30, ChronoUnit.DAYS),
                            sessionEnd.plus(1, ChronoUnit.DAYS)
                        )
                    ).maxByOrNull { it.time }?.vo2MillilitersPerMinuteKilogram
                } catch (e: Exception) {
                    Log.w(TAG, "Could not read VO2 max: ${e.message}")
                    null
                }

                val durationSec = ChronoUnit.SECONDS.between(sessionStart, sessionEnd)
                val hasAnyData =
                    routePoints.isNotEmpty() || hrSeries.isNotEmpty() || speedSeries.isNotEmpty()
                if (!hasAnyData || durationSec < MIN_SYNCABLE_DURATION_SEC) {
                    skippedEmpty++
                    Log.d(
                        TAG,
                        "Skipping empty session ${record.metadata.id}: " +
                            "${durationSec}s, route=${routePoints.size}, hr=${hrSeries.size}"
                    )
                    continue
                }

                val sportName = SPORT_TYPE_NAMES[record.exerciseType] ?: run {
                    // Surface the raw type so an unmapped activity can be given
                    // a proper name rather than staying generic forever.
                    Log.d(TAG, "Unmapped exercise type ${record.exerciseType} -> '$DEFAULT_SPORT_NAME'")
                    DEFAULT_SPORT_NAME
                }

                results.add(
                    WorkoutSessionData(
                        sessionId = record.metadata.id,
                        title = record.title ?: sportName.replaceFirstChar { it.uppercase() },
                        sportType = sportName,
                        startTime = sessionStart.toString(),
                        endTime = sessionEnd.toString(),
                        distanceMeters = distance,
                        durationSec = durationSec.toDouble(),
                        caloriesKcal = calories,
                        elevationGainM = elevation,
                        steps = steps,
                        vo2Max = vo2,
                        routePoints = routePoints,
                        heartRateSeries = hrSeries,
                        speedSeries = speedSeries,
                        cadenceSeries = cadenceSeries,
                        notes = record.notes
                    )
                )
            }
            if (skippedEmpty > 0) {
                Log.d(TAG, "Skipped $skippedEmpty session(s) with no usable data.")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reading records from Health Connect: ${e.message}", e)
        }

        return results
    }

    suspend fun fetchDailyWellness(daysBack: Long = 14): List<DailyWellnessData> {
        healthConnectClient ?: return emptyList()
        val results = mutableListOf<DailyWellnessData>()

        for (i in 0..daysBack) {
            val date = LocalDate.now().minusDays(i)
            val dayStart = date.atStartOfDay(ZoneId.systemDefault()).toInstant()
            val dayEnd = date.plusDays(1).atStartOfDay(ZoneId.systemDefault()).toInstant()
            val dayRange = TimeRangeFilter.between(dayStart, dayEnd)

            val hrv = try {
                readAll(HeartRateVariabilityRmssdRecord::class, dayRange)
                    .map { it.heartRateVariabilityMillis }
                    .takeIf { it.isNotEmpty() }?.average()
            } catch (e: Exception) { null }

            // The lowest reading of the day is a far better resting-heart-rate
            // proxy than the mean: devices log these throughout the day, so the
            // average is dominated by ordinary daytime activity.
            val rhr = try {
                readAll(RestingHeartRateRecord::class, dayRange)
                    .map { it.beatsPerMinute }
                    .takeIf { it.isNotEmpty() }?.min()?.toInt()
            } catch (e: Exception) { null }

            val sleepSec = try {
                readAll(
                    SleepSessionRecord::class,
                    TimeRangeFilter.between(dayStart.minus(6, ChronoUnit.HOURS), dayEnd)
                ).distinctBy { it.startTime to it.endTime }
                    .sumOf { ChronoUnit.SECONDS.between(it.startTime, it.endTime) }
                    .toDouble().takeIf { it > 0 }
            } catch (e: Exception) { null }

            val steps = try {
                aggregateOrNull(StepsRecord.COUNT_TOTAL, dayStart, dayEnd, emptySet())?.toInt()
            } catch (e: Exception) { null }

            val vo2 = try {
                readAll(Vo2MaxRecord::class, dayRange)
                    .map { it.vo2MillilitersPerMinuteKilogram }
                    .takeIf { it.isNotEmpty() }?.average()
            } catch (e: Exception) { null }

            results.add(
                DailyWellnessData(
                    date = date.toString(),
                    restingHr = rhr,
                    hrvRmssd = hrv,
                    sleepDurationSec = sleepSec,
                    sleepScore = null,
                    vo2Max = vo2,
                    steps = steps
                )
            )
        }
        return results
    }
}
