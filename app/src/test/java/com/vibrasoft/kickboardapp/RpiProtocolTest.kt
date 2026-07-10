package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.bluetooth.RpiMessage
import com.vibrasoft.kickboardapp.bluetooth.RpiProtocol
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RpiProtocolTest {

    @Test
    fun buildSetModeCommand_collect() {
        assertEquals(
            """{"cmd":"SET_MODE","mode":"COLLECT"}""",
            RpiProtocol.buildSetModeCommand("COLLECT")
        )
    }

    @Test
    fun buildSetModeCommand_demo() {
        assertEquals(
            """{"cmd":"SET_MODE","mode":"DEMO"}""",
            RpiProtocol.buildSetModeCommand("DEMO")
        )
    }

    @Test
    fun buildStartCommand() {
        assertEquals("""{"cmd":"START"}""", RpiProtocol.buildStartCommand())
    }

    @Test
    fun buildStopCommand() {
        assertEquals("""{"cmd":"STOP"}""", RpiProtocol.buildStopCommand())
    }

    @Test
    fun buildListFilesCommand() {
        assertEquals("""{"cmd":"LIST_FILES"}""", RpiProtocol.buildListFilesCommand())
    }

    @Test
    fun buildRenameCommand_plainNames() {
        assertEquals(
            """{"cmd":"RENAME","old":"old.csv","new":"new.csv"}""",
            RpiProtocol.buildRenameCommand("old.csv", "new.csv")
        )
    }

    @Test
    fun buildRenameCommand_escapesQuote() {
        assertEquals(
            "{\"cmd\":\"RENAME\",\"old\":\"file\\\"1\\\".csv\",\"new\":\"file2.csv\"}",
            RpiProtocol.buildRenameCommand("file\"1\".csv", "file2.csv")
        )
    }

    @Test
    fun buildMemoCommand_plainText() {
        assertEquals(
            """{"cmd":"MEMO","file":"road.csv","memo":"보도블럭 구간"}""",
            RpiProtocol.buildMemoCommand("road.csv", "보도블럭 구간")
        )
    }

    @Test
    fun buildMemoCommand_escapesBackslash() {
        assertEquals(
            "{\"cmd\":\"MEMO\",\"file\":\"road.csv\",\"memo\":\"C:\\\\Users\\\\test\"}",
            RpiProtocol.buildMemoCommand("road.csv", "C:\\Users\\test")
        )
    }

    @Test
    fun buildNewFileName_appendsTypeAndCondition() {
        assertEquals(
            "20260630_143022_아스팔트_불량.csv",
            RpiProtocol.buildNewFileName("20260630_143022.csv", "아스팔트", "불량")
        )
    }

    @Test
    fun buildNewFileName_customType() {
        assertEquals(
            "20260630_143022_자갈길_불량.csv",
            RpiProtocol.buildNewFileName("20260630_143022.csv", "자갈길", "불량")
        )
    }

    @Test
    fun parseMessage_ack() {
        val result = RpiProtocol.parseMessage("""{"type":"ACK","cmd":"START","ok":true}""")
        assertEquals(RpiMessage.Ack("START", true), result)
    }

    @Test
    fun parseMessage_status() {
        val result = RpiProtocol.parseMessage(
            """{"type":"STATUS","speed":15.3,"roadType":"아스팔트"}"""
        )
        assertEquals(RpiMessage.Status(15.3f, "아스팔트"), result)
    }

    @Test
    fun parseMessage_files() {
        val result = RpiProtocol.parseMessage(
            """{"type":"FILES","files":["a.csv","b.csv"]}"""
        )
        assertEquals(RpiMessage.Files(listOf("a.csv", "b.csv")), result)
    }

    @Test
    fun parseMessage_error() {
        val result = RpiProtocol.parseMessage(
            """{"type":"ERROR","cmd":"RENAME","message":"file not found"}"""
        )
        assertEquals(RpiMessage.Error("RENAME", "file not found"), result)
    }

    @Test
    fun parseMessage_malformedJson_returnsNull() {
        assertNull(RpiProtocol.parseMessage("not json"))
    }

    @Test
    fun parseMessage_unknownType_returnsNull() {
        assertNull(RpiProtocol.parseMessage("""{"type":"UNKNOWN"}"""))
    }
}
