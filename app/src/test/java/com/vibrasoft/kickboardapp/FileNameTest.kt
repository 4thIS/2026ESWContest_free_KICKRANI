package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.gps.GpsLogger
import org.junit.Assert.assertEquals
import org.junit.Test

class FileNameTest {

    @Test
    fun buildNewFileName_appendsTypeAndCondition() {
        val result = GpsLogger.buildNewFileName(
            "20260630_143022.csv", "아스팔트", "불량"
        )
        assertEquals("20260630_143022_아스팔트_불량.csv", result)
    }

    @Test
    fun buildNewFileName_customType() {
        val result = GpsLogger.buildNewFileName(
            "20260630_143022.csv", "자갈길", "불량"
        )
        assertEquals("20260630_143022_자갈길_불량.csv", result)
    }
}
