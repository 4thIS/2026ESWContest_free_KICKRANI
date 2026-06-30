package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.network.DeviceApi
import com.vibrasoft.kickboardapp.network.GpsPoint
import org.junit.Assert.assertEquals
import org.junit.Test

class DeviceApiTest {

    @Test
    fun buildSpeedLogJson_correctFormat() {
        val points = listOf(
            GpsPoint(1000L, 12.4f),
            GpsPoint(2000L, 13.1f)
        )
        val json = DeviceApi.buildSpeedLogJson(points)
        assertEquals(
            """[{"timestamp":1000,"speed":12.4},{"timestamp":2000,"speed":13.1}]""",
            json
        )
    }

    @Test
    fun buildMemoJson_plainText_noEscaping() {
        val result = DeviceApi.buildMemoJson("road.csv", "일반 메모")
        assertEquals("""{"file":"road.csv","memo":"일반 메모"}""", result)
    }

    @Test
    fun buildMemoJson_doubleQuoteInMemo_escaped() {
        val result = DeviceApi.buildMemoJson("road.csv", "도로 \"위험\" 구간")
        assertEquals("{\"file\":\"road.csv\",\"memo\":\"도로 \\\"위험\\\" 구간\"}", result)
    }

    @Test
    fun buildMemoJson_backslashInMemo_escaped() {
        val result = DeviceApi.buildMemoJson("road.csv", "경로 C:\\Users\\test")
        assertEquals("{\"file\":\"road.csv\",\"memo\":\"경로 C:\\\\Users\\\\test\"}", result)
    }

    @Test
    fun buildMemoJson_backslashAndQuote_bothEscaped() {
        val result = DeviceApi.buildMemoJson("road.csv", "값: \\\"quoted\\\"")
        assertEquals("{\"file\":\"road.csv\",\"memo\":\"값: \\\\\\\"quoted\\\\\\\"\"}", result)
    }

    @Test
    fun buildRenameJson_plainNames_noEscaping() {
        val result = DeviceApi.buildRenameJson("old.csv", "new.csv")
        assertEquals("""{"old":"old.csv","new":"new.csv"}""", result)
    }

    @Test
    fun buildRenameJson_doubleQuoteInName_escaped() {
        val result = DeviceApi.buildRenameJson("file\"1\".csv", "file2.csv")
        assertEquals("{\"old\":\"file\\\"1\\\".csv\",\"new\":\"file2.csv\"}", result)
    }

    @Test
    fun buildRenameJson_backslashInName_escaped() {
        val result = DeviceApi.buildRenameJson("path\\file.csv", "file.csv")
        assertEquals("{\"old\":\"path\\\\file.csv\",\"new\":\"file.csv\"}", result)
    }
}
