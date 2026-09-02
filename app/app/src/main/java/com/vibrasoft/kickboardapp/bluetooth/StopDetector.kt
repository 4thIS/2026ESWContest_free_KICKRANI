package com.vibrasoft.kickboardapp.bluetooth

/**
 * 차량이 실제로 멈췄는지를 **이동거리로** 판정한다.
 *
 * Pi는 STOP 직후 `SpeedController.stop()`이 `current_speed`에 0을 대입하고 IDLE에서는
 * `update()`를 부르지 않아, STATUS의 `speed`로는 관성 구간을 볼 수 없다. 반면 `distance`는
 * `encoder.distance_m()`을 상태와 무관하게 읽으므로 굴러가는 동안 계속 늘어난다.
 *
 * 엔코더 해상도가 펄스당 약 10.2cm(자석 4개 N-S 교대·래치형 → PPR=2, 둘레 0.204m)라
 * 주행 중에도 같은 거리가 몇 번 연속으로 올 수 있다. 그래서 한 번 같다고 바로 멈춘 것으로
 * 보지 않고, [stillSamplesToStop]회 연속으로 변화가 없을 때만 정지로 판정한다.
 * 기본값 5는 5Hz 기준 1초로, Pi의 `ENCODER_STOP_TIMEOUT_S = 1.0`과 같은 기준이다.
 */
class StopDetector(
    private val stillSamplesToStop: Int = STILL_SAMPLES_TO_STOP,
    private val epsilonM: Float = EPSILON_M
) {
    private var lastDistance: Float? = null
    private var stillCount = 0

    var isStopped = false
        private set

    fun onDistance(distanceM: Float?) {
        if (distanceM == null) return          // 거리가 없는 STATUS는 판정에 쓰지 않는다
        val prev = lastDistance
        lastDistance = distanceM
        if (prev == null) return               // 첫 표본은 비교 대상이 없다
        if (kotlin.math.abs(distanceM - prev) < epsilonM) {
            stillCount++
            if (stillCount >= stillSamplesToStop) isStopped = true
        } else {
            stillCount = 0
        }
    }

    fun reset() {
        lastDistance = null
        stillCount = 0
        isStopped = false
    }

    companion object {
        const val STILL_SAMPLES_TO_STOP = 5    // 5Hz × 5 = 1초
        const val EPSILON_M = 0.01f            // 펄스당 10.2cm보다 훨씬 작게
    }
}
