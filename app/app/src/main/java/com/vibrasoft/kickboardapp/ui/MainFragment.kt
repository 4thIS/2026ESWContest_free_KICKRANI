package com.vibrasoft.kickboardapp.ui

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.vibrasoft.kickboardapp.MainActivity
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.bluetooth.RpiMessage
import com.vibrasoft.kickboardapp.bluetooth.RpiProtocol
import com.vibrasoft.kickboardapp.bluetooth.SessionState
import com.vibrasoft.kickboardapp.bluetooth.StopDetector
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.data.SpeedFormat
import com.vibrasoft.kickboardapp.databinding.FragmentMainBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainFragment : Fragment(R.layout.fragment_main) {
    private var _binding: FragmentMainBinding? = null
    private val binding get() = _binding!!

    private lateinit var rpiProtocol: RpiProtocol

    private lateinit var settings: AppSettings

    private var isConnected = false
    private val session = SessionState()
    private var timerJob: Job? = null
    private var pendingTimeoutJob: Job? = null
    private var elapsedSeconds = 0L

    // 이동거리는 Pi가 엔코더 누적값으로 보내므로, 출발 시점을 기준으로 빼서 주행 단위로 만든다.
    private val stopDetector = StopDetector()
    private var distanceBaseM: Float? = null
    private var awaitingDistanceBase = false

    private val statusCallback: (RpiMessage.Status) -> Unit = { status -> updateStatusDisplay(status) }
    private val disconnectedCallback: () -> Unit = { handleDisconnected() }
    private val ackCallback: (String, Boolean) -> Unit = { cmd, ok -> handleAck(cmd, ok) }
    private val onErrorCallback: (String, String) -> Unit = { cmd, message ->
        _binding?.let {
            session.onError(cmd)
            if (cmd == "START" || cmd == "STOP") {
                pendingTimeoutJob?.cancel()
                updateButtonStates()
            }
            Toast.makeText(requireContext(), "$cmd 실패: $message", Toast.LENGTH_SHORT).show()
        }
    }
    private val connectedCallback: () -> Unit = { refreshConnectionState() }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentMainBinding.bind(view)
        rpiProtocol = (requireActivity() as MainActivity).rpiProtocol
        settings = AppSettings(requireContext())

        rpiProtocol.addStatusListener(statusCallback)
        rpiProtocol.addDisconnectedListener(disconnectedCallback)
        rpiProtocol.addAckListener(ackCallback)
        rpiProtocol.addErrorListener(onErrorCallback)
        rpiProtocol.addConnectedListener(connectedCallback)

        binding.btnSession.setOnClickListener {
            // 연타 재진입 차단: ACK/ERROR/타임아웃까지 pending으로 잠금
            if (session.isRunning) stopSession() else startSession()
        }
    }

    override fun onResume() {
        super.onResume()
        refreshConnectionState()
    }

    private fun refreshConnectionState() {
        val connector = (requireActivity() as MainActivity).bluetoothConnector
        isConnected = connector.isConnected()
        binding.tvConnection.text = if (isConnected) "● 연결됨" else "○ 미연결"
        updateButtonStates()
    }

    private fun startSession() {
        val mode = if (binding.rbDemo.isChecked) "DEMO" else "COLLECT"
        resetTelemetryDisplay()
        session.startRequested()
        updateButtonStates()
        viewLifecycleOwner.lifecycleScope.launch {
            rpiProtocol.sendCommand(RpiProtocol.buildSetModeCommand(mode))
            val sent = rpiProtocol.sendCommand(RpiProtocol.buildStartCommand())
            if (!sent) {
                abortPending("출발 명령 전송 실패")
            } else {
                startPendingTimeout()
            }
        }
    }

    private fun stopSession() {
        session.stopRequested()
        updateButtonStates()
        viewLifecycleOwner.lifecycleScope.launch {
            val sent = rpiProtocol.sendCommand(RpiProtocol.buildStopCommand())
            if (!sent) {
                abortPending("정지 명령 전송 실패")
            } else {
                startPendingTimeout()
            }
        }
    }

    // 세션 상태는 Pi의 ACK로만 확정한다 (START 거부 시 '실행 중' 오표시 방지)
    private fun handleAck(cmd: String, ok: Boolean) {
        if (cmd != "START" && cmd != "STOP") return
        pendingTimeoutJob?.cancel()
        val wasRunning = session.isRunning
        session.onAck(cmd, ok)
        _binding ?: return
        if (!wasRunning && session.isRunning) {
            // 출발 — 경과시간·이동거리를 0부터 다시 센다
            elapsedSeconds = 0L
            distanceBaseM = null
            awaitingDistanceBase = true
            stopDetector.reset()
            _binding?.tvDistance?.text = "0.0 m"
            startTimer()
        }
        // 정지 ACK를 받아도 타이머를 멈추지 않는다 — 관성으로 굴러가는 동안 계속 잰다.
        // 실제 정지는 updateStatusDisplay가 거리로 판정해 freezeTrip()으로 끝낸다.
        updateButtonStates()
    }

    private fun startPendingTimeout() {
        pendingTimeoutJob?.cancel()
        pendingTimeoutJob = viewLifecycleOwner.lifecycleScope.launch {
            delay(PENDING_TIMEOUT_MS)
            abortPending("응답 없음 (Pi 연결 상태 확인)")
        }
    }

    private fun abortPending(message: String) {
        session.onTimeout()
        _binding?.let {
            updateButtonStates()
            Toast.makeText(requireContext(), message, Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateStatusDisplay(status: RpiMessage.Status) {
        val b = _binding ?: return
        b.tvSpeed.text = SpeedFormat.format(status.speed, settings.speedUnit)
        updateTripDistance(b, status.distance)
        // 누적 거리는 Pi 원값 그대로 — 세션과 무관하게 항상 갱신한다
        b.tvTotalDistance.text = status.distance?.let { "%.1f m".format(it) } ?: "- m"
        b.tvVibration.text = status.vibration?.let { "%.2f".format(it) } ?: "-"
        // 노면 유형은 시연모드에서만 보인다. Pi는 STOP 후에도 마지막 추론값을 계속
        // 보내므로(controller._safe_stop이 road를 안 지움), 수집모드에서 직전 시연의
        // 값이 남아 표시되는 것을 여기서 막는다.
        if (b.rbDemo.isChecked && status.roadType != null) {
            b.rowRoadType.visibility = View.VISIBLE
            b.tvRoadType.text = status.roadType
        } else {
            b.rowRoadType.visibility = View.GONE
        }
    }

    /** 주행 거리 = Pi 누적거리 − 출발 시점 기준값. 감속이 끝나면 값을 동결한다. */
    private fun updateTripDistance(b: FragmentMainBinding, rawDistance: Float?) {
        val measuring = session.isRunning || session.isWindingDown
        if (!measuring) return                      // 동결 — 마지막 값 유지

        if (awaitingDistanceBase && rawDistance != null) {
            distanceBaseM = rawDistance
            awaitingDistanceBase = false
        }
        val base = distanceBaseM
        if (rawDistance != null && base != null) {
            b.tvDistance.text = "%.1f m".format((rawDistance - base).coerceAtLeast(0f))
        }

        if (session.isWindingDown) {
            stopDetector.onDistance(rawDistance)
            if (stopDetector.isStopped) freezeTrip()
        }
    }

    /** 관성 구간 종료 — 경과시간·이동거리를 다음 출발까지 그대로 둔다. */
    private fun freezeTrip() {
        session.windDownFinished()
        timerJob?.cancel()
        updateButtonStates()
    }

    private fun resetTelemetryDisplay() {
        val b = _binding ?: return
        b.tvSpeed.text = SpeedFormat.format(null, settings.speedUnit)
        b.tvDistance.text = "- m"       // 주행 거리만 초기화 — 누적은 Pi 값이라 그대로 둔다
        b.tvVibration.text = "-"
        b.rowRoadType.visibility = View.GONE
    }

    private fun handleDisconnected() {
        _binding?.let { b ->
            isConnected = false
            session.onDisconnected()
            timerJob?.cancel()
            pendingTimeoutJob?.cancel()
            stopDetector.reset()
            distanceBaseM = null
            awaitingDistanceBase = false
            b.tvConnection.text = "○ 미연결"
            resetTelemetryDisplay()
            updateButtonStates()
        }
    }

    private fun startTimer() {
        timerJob?.cancel()
        timerJob = viewLifecycleOwner.lifecycleScope.launch {
            while (true) {
                delay(1000)
                elapsedSeconds++
                val h = elapsedSeconds / 3600
                val m = (elapsedSeconds % 3600) / 60
                val s = elapsedSeconds % 60
                binding.tvTimer.text = "%02d:%02d:%02d".format(h, m, s)
            }
        }
    }

    private fun updateButtonStates() {
        val idle = !session.isRunning && !session.isPending
        binding.rbCollect.isEnabled = isConnected && idle
        binding.rbDemo.isEnabled = isConnected && idle
        binding.btnSession.isEnabled = isConnected && !session.isPending
        binding.btnSession.text = if (session.isRunning) "정지" else "출발"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        timerJob?.cancel()
        pendingTimeoutJob?.cancel()
        rpiProtocol.removeStatusListener(statusCallback)
        rpiProtocol.removeDisconnectedListener(disconnectedCallback)
        rpiProtocol.removeAckListener(ackCallback)
        rpiProtocol.removeErrorListener(onErrorCallback)
        rpiProtocol.removeConnectedListener(connectedCallback)
        _binding = null
    }

    companion object {
        private const val PENDING_TIMEOUT_MS = 3000L
    }
}
