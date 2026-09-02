package com.vibrasoft.kickboardapp

import com.vibrasoft.kickboardapp.bluetooth.StopDetector
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 정지 판정은 거리로 한다.
 * Pi가 STOP 직후 speed를 0으로 대입해버려(SpeedController.stop) 속도로는 관성 구간을
 * 볼 수 없지만, distance는 엔코더를 직접 읽으므로 굴러가는 동안 계속 늘어난다.
 */
class StopDetectorTest {

    private fun detector() = StopDetector(stillSamplesToStop = 5)

    @Test
    fun `초기에는 정지로 보지 않는다`() {
        assertFalse(detector().isStopped)
    }

    @Test
    fun `거리가 계속 늘면 정지가 아니다`() {
        val d = detector()
        listOf(1.0f, 1.1f, 1.2f, 1.3f, 1.4f, 1.5f, 1.6f, 1.7f).forEach { d.onDistance(it) }
        assertFalse(d.isStopped)
    }

    @Test
    fun `엔코더 해상도 때문에 값이 잠깐 멈춰도 정지로 보지 않는다`() {
        // PPR=2·둘레 0.204m → 펄스당 10.2cm. 5Hz면 주행 중에도 같은 값이 두세 번 반복된다.
        val d = detector()
        listOf(1.0f, 1.0f, 1.0f, 1.102f, 1.102f, 1.102f, 1.204f).forEach { d.onDistance(it) }
        assertFalse(d.isStopped)
    }

    @Test
    fun `연속 5회 거리가 그대로면 정지로 판정한다`() {
        val d = detector()
        d.onDistance(2.0f)
        repeat(5) { d.onDistance(2.0f) }
        assertTrue(d.isStopped)
    }

    @Test
    fun `판정 직전에 다시 움직이면 카운트가 초기화된다`() {
        val d = detector()
        d.onDistance(2.0f)
        repeat(4) { d.onDistance(2.0f) }
        assertFalse(d.isStopped)
        d.onDistance(2.102f)
        repeat(4) { d.onDistance(2.102f) }
        assertFalse(d.isStopped)
    }

    @Test
    fun `1cm 미만 흔들림은 움직인 것으로 치지 않는다`() {
        val d = detector()
        d.onDistance(2.0f)
        repeat(5) { d.onDistance(2.001f) }
        assertTrue(d.isStopped)
    }

    @Test
    fun `distance가 없는 STATUS는 판정에 영향을 주지 않는다`() {
        val d = detector()
        d.onDistance(2.0f)
        repeat(5) { d.onDistance(null) }
        assertFalse(d.isStopped)
    }

    @Test
    fun `reset하면 처음 상태로 돌아간다`() {
        val d = detector()
        d.onDistance(2.0f)
        repeat(5) { d.onDistance(2.0f) }
        assertTrue(d.isStopped)
        d.reset()
        assertFalse(d.isStopped)
    }
}
