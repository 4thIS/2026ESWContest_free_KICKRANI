package com.vibrasoft.kickboardapp.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

data class GpsPoint(val timestamp: Long, val speed: Float)

class DeviceApi(private val deviceIp: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val baseUrl get() = "http://$deviceIp"
    private val json = "application/json".toMediaType()

    companion object {
        private fun escapeJsonString(s: String): String =
            s.replace("\\", "\\\\").replace("\"", "\\\"")

        fun buildSpeedLogJson(points: List<GpsPoint>): String {
            val entries = points.joinToString(",") {
                """{"timestamp":${it.timestamp},"speed":${it.speed}}"""
            }
            return "[$entries]"
        }

        fun buildMemoJson(file: String, memo: String): String =
            """{"file":"${escapeJsonString(file)}","memo":"${escapeJsonString(memo)}"}"""

        fun buildRenameJson(old: String, new: String): String =
            """{"old":"${escapeJsonString(old)}","new":"${escapeJsonString(new)}"}"""
    }

    suspend fun sync(timestamp: Long): Boolean = post(
        "/sync", """{"timestamp":$timestamp}"""
    )

    suspend fun start(): Boolean = post("/start", "")

    suspend fun stop(): Boolean = post("/stop", "")

    suspend fun sendSpeedLog(points: List<GpsPoint>): Boolean = post(
        "/speed-log", buildSpeedLogJson(points)
    )

    suspend fun getFiles(): List<String> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder().url("$baseUrl/files").get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext emptyList()
                val body = response.body?.string() ?: return@withContext emptyList()
                // 응답 형식: ["file1.csv","file2.csv"]
                body.trim('[', ']')
                    .split(",")
                    .map { it.trim().trim('"') }
                    .filter { it.endsWith(".csv") }
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    suspend fun renameFile(oldName: String, newName: String): Boolean = post(
        "/rename", buildRenameJson(oldName, newName)
    )

    suspend fun addMemo(fileName: String, memo: String): Boolean = post(
        "/memo", buildMemoJson(fileName, memo)
    )

    private suspend fun post(path: String, bodyStr: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val body = bodyStr.toRequestBody(json)
                val request = Request.Builder().url("$baseUrl$path").post(body).build()
                client.newCall(request).execute().use { it.isSuccessful }
            } catch (e: Exception) {
                false
            }
        }
}
