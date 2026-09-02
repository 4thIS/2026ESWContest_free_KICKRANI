package com.vibrasoft.kickboardapp.bluetooth

/**
 * 세션 실행 상태 — Pi의 ACK/ERROR 응답을 근거로만 전이한다.
 * (명령 전송 자체로는 상태를 바꾸지 않는다: START가 거부돼도
 * 앱이 "실행 중"으로 잘못 표시하던 탈동기화 방지)
 */
class SessionState {
    var isRunning = false
        private set
    var isPending = false
        private set

    /**
     * 정지 버튼을 눌렀지만 차량이 아직 굴러가는 구간.
     * 이때도 경과시간·이동거리를 계속 재고, 실제로 멈추면 [windDownFinished]로 동결한다.
     */
    var isWindingDown = false
        private set

    fun startRequested() {
        isPending = true
        isWindingDown = false
    }

    fun stopRequested() {
        isPending = true
    }

    fun onAck(cmd: String, ok: Boolean) {
        when (cmd) {
            "START" -> {
                isPending = false
                if (ok) isRunning = true
            }
            "STOP" -> {
                isPending = false
                if (ok) {
                    isRunning = false
                    isWindingDown = true        // 관성 구간 — 멈출 때까지 계속 측정
                }
            }
        }
    }

    fun onError(cmd: String) {
        if (cmd == "START" || cmd == "STOP") isPending = false
    }

    fun onTimeout() {
        isPending = false
    }

    /** 차량이 실제로 멈춤 — 경과시간·이동거리를 동결한다. */
    fun windDownFinished() {
        isWindingDown = false
    }

    fun onDisconnected() {
        isRunning = false
        isPending = false
        isWindingDown = false
    }
}
