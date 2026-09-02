package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.data.SpeedFormat
import com.vibrasoft.kickboardapp.data.SpeedUnit
import org.junit.Assert.assertEquals
import org.junit.Test

class SpeedFormatTest {

    @Test
    fun `km_h 선택 시 m_s 원값을 3_6배 환산해 표시한다`() {
        assertEquals("1.4 km/h", SpeedFormat.format(0.4f, SpeedUnit.KMH))
    }

    @Test
    fun `m_s 선택 시 원값 그대로 표시한다`() {
        assertEquals("0.4 m/s", SpeedFormat.format(0.4f, SpeedUnit.MPS))
    }

    @Test
    fun `null이면 단위만 붙은 플레이스홀더를 반환한다`() {
        assertEquals("- km/h", SpeedFormat.format(null, SpeedUnit.KMH))
        assertEquals("- m/s", SpeedFormat.format(null, SpeedUnit.MPS))
    }

    @Test
    fun `0은 정상 표시한다`() {
        assertEquals("0.0 km/h", SpeedFormat.format(0.0f, SpeedUnit.KMH))
        assertEquals("0.0 m/s", SpeedFormat.format(0.0f, SpeedUnit.MPS))
    }
}
