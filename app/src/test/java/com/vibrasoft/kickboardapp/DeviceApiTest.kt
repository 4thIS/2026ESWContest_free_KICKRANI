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
}
