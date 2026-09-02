package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.bluetooth.SessionState
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionStateTest {

    @Test
    fun `초기 상태는 정지·비대기`() {
        val s = SessionState()
        assertFalse(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `START 전송 직후에는 대기 상태이고 아직 실행 중이 아니다`() {
        val s = SessionState()
        s.startRequested()
        assertTrue(s.isPending)
        assertFalse(s.isRunning)
    }

    @Test
    fun `START ACK 성공 시에만 실행 중으로 전이한다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("START", ok = true)
        assertTrue(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `START ACK 실패면 정지 상태를 유지한다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("START", ok = false)
        assertFalse(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `START ERROR 응답이면 정지 상태를 유지한다`() {
        val s = SessionState()
        s.startRequested()
        s.onError("START")
        assertFalse(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `STOP ACK 성공 시 정지로 전이한다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("START", ok = true)
        s.stopRequested()
        assertTrue(s.isPending)
        s.onAck("STOP", ok = true)
        assertFalse(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `STOP ERROR면 실행 중 상태를 유지한다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("START", ok = true)
        s.stopRequested()
        s.onError("STOP")
        assertTrue(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `무관한 명령의 ACK는 세션 상태에 영향 없다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("RENAME", ok = true)
        assertTrue(s.isPending)
        assertFalse(s.isRunning)
    }

    @Test
    fun `연결 끊김이면 무조건 정지·비대기로 리셋한다`() {
        val s = SessionState()
        s.startRequested()
        s.onAck("START", ok = true)
        s.onDisconnected()
        assertFalse(s.isRunning)
        assertFalse(s.isPending)
    }

    @Test
    fun `응답 타임아웃이면 대기만 해제하고 상태는 유지한다`() {
        val s = SessionState()
        s.startRequested()
        s.onTimeout()
        assertFalse(s.isPending)
        assertFalse(s.isRunning)
    }

    @Test
    fun `STOP ACK 직후에는 감속 측정 중이다`() {
        val s = SessionState()
        s.startRequested(); s.onAck("START", ok = true)
        s.stopRequested(); s.onAck("STOP", ok = true)
        assertFalse(s.isRunning)
        assertTrue(s.isWindingDown)
    }

    @Test
    fun `감속이 끝나면 측정을 멈춘다`() {
        val s = SessionState()
        s.startRequested(); s.onAck("START", ok = true)
        s.stopRequested(); s.onAck("STOP", ok = true)
        s.windDownFinished()
        assertFalse(s.isWindingDown)
        assertFalse(s.isRunning)
    }

    @Test
    fun `STOP이 거부되면 감속 측정에 들어가지 않는다`() {
        val s = SessionState()
        s.startRequested(); s.onAck("START", ok = true)
        s.stopRequested(); s.onError("STOP")
        assertTrue(s.isRunning)
        assertFalse(s.isWindingDown)
    }

    @Test
    fun `재출발하면 감속 상태가 해제된다`() {
        val s = SessionState()
        s.startRequested(); s.onAck("START", ok = true)
        s.stopRequested(); s.onAck("STOP", ok = true)
        assertTrue(s.isWindingDown)
        s.startRequested(); s.onAck("START", ok = true)
        assertTrue(s.isRunning)
        assertFalse(s.isWindingDown)
    }

    @Test
    fun `연결이 끊기면 감속 상태도 해제된다`() {
        val s = SessionState()
        s.startRequested(); s.onAck("START", ok = true)
        s.stopRequested(); s.onAck("STOP", ok = true)
        s.onDisconnected()
        assertFalse(s.isWindingDown)
    }
}
