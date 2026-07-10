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
import com.vibrasoft.kickboardapp.databinding.FragmentMainBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainFragment : Fragment(R.layout.fragment_main) {
    private var _binding: FragmentMainBinding? = null
    private val binding get() = _binding!!

    private lateinit var rpiProtocol: RpiProtocol

    private var isConnected = false
    private var isSessionRunning = false
    private var timerJob: Job? = null
    private var elapsedSeconds = 0L

    private val statusCallback: (RpiMessage.Status) -> Unit = { status -> updateStatusDisplay(status) }
    private val disconnectedCallback: () -> Unit = { handleDisconnected() }
    private val onErrorCallback: (String, String) -> Unit = { cmd, message ->
        _binding?.let {
            Toast.makeText(requireContext(), "$cmd 실패: $message", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentMainBinding.bind(view)
        rpiProtocol = (requireActivity() as MainActivity).rpiProtocol

        rpiProtocol.addStatusListener(statusCallback)
        rpiProtocol.addDisconnectedListener(disconnectedCallback)
        rpiProtocol.addErrorListener(onErrorCallback)

        binding.btnSession.setOnClickListener {
            if (isSessionRunning) stopSession() else startSession()
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
        viewLifecycleOwner.lifecycleScope.launch {
            rpiProtocol.sendCommand(RpiProtocol.buildSetModeCommand(mode))
            rpiProtocol.sendCommand(RpiProtocol.buildStartCommand())
            isSessionRunning = true
            elapsedSeconds = 0L
            startTimer()
            updateButtonStates()
        }
    }

    private fun stopSession() {
        viewLifecycleOwner.lifecycleScope.launch {
            rpiProtocol.sendCommand(RpiProtocol.buildStopCommand())
            isSessionRunning = false
            timerJob?.cancel()
            updateButtonStates()
        }
    }

    private fun updateStatusDisplay(status: RpiMessage.Status) {
        val b = _binding ?: return
        b.tvSpeed.text = "%.1f km/h".format(status.speed)
        b.tvDistance.text = status.distance?.let { "%.1f m".format(it) } ?: "- m"
        b.tvVibration.text = status.vibration?.let { "%.2f".format(it) } ?: "-"
        if (status.roadType != null) {
            b.rowRoadType.visibility = View.VISIBLE
            b.tvRoadType.text = status.roadType
        } else {
            b.rowRoadType.visibility = View.GONE
        }
    }

    private fun resetTelemetryDisplay() {
        val b = _binding ?: return
        b.tvSpeed.text = "- km/h"
        b.tvDistance.text = "- m"
        b.tvVibration.text = "-"
        b.rowRoadType.visibility = View.GONE
    }

    private fun handleDisconnected() {
        _binding?.let { b ->
            isConnected = false
            isSessionRunning = false
            timerJob?.cancel()
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
        binding.rbCollect.isEnabled = isConnected && !isSessionRunning
        binding.rbDemo.isEnabled = isConnected && !isSessionRunning
        binding.btnSession.isEnabled = isConnected
        binding.btnSession.text = if (isSessionRunning) "정지" else "출발"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        timerJob?.cancel()
        rpiProtocol.removeStatusListener(statusCallback)
        rpiProtocol.removeDisconnectedListener(disconnectedCallback)
        rpiProtocol.removeErrorListener(onErrorCallback)
        _binding = null
    }
}
