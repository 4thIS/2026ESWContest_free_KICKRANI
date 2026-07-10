package com.vibrasoft.kickboardapp.ui

import android.bluetooth.BluetoothDevice
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.vibrasoft.kickboardapp.MainActivity
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.bluetooth.RpiMessage
import com.vibrasoft.kickboardapp.bluetooth.RpiProtocol
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.databinding.FragmentMainBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainFragment : Fragment(R.layout.fragment_main) {
    private var _binding: FragmentMainBinding? = null
    private val binding get() = _binding!!

    private lateinit var settings: AppSettings
    private lateinit var rpiProtocol: RpiProtocol

    private var isConnected = false
    private var isSessionRunning = false
    private var timerJob: Job? = null
    private var elapsedSeconds = 0L

    private val devicePicker = BluetoothDevicePicker(
        fragment = this,
        connectorProvider = { (requireActivity() as MainActivity).bluetoothConnector },
        onDeviceSelected = { device -> connectTo(device) }
    )

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
        settings = AppSettings(requireContext())
        rpiProtocol = (requireActivity() as MainActivity).rpiProtocol

        rpiProtocol.addStatusListener(statusCallback)
        rpiProtocol.addDisconnectedListener(disconnectedCallback)
        rpiProtocol.addErrorListener(onErrorCallback)

        binding.btnConnect.setOnClickListener { devicePicker.requestPick() }
        binding.rgMode.setOnCheckedChangeListener { _, _ -> updateButtonStates() }
        binding.btnSession.setOnClickListener {
            if (isSessionRunning) stopSession() else startSession()
        }

        val connector = (requireActivity() as MainActivity).bluetoothConnector
        isConnected = connector.isConnected()
        binding.tvConnection.text = if (isConnected) "● 연결됨" else "○ 미연결"

        updateButtonStates()
    }

    private fun connectTo(device: BluetoothDevice) {
        binding.tvConnection.text = "연결 중..."
        viewLifecycleOwner.lifecycleScope.launch {
            val connector = (requireActivity() as MainActivity).bluetoothConnector
            val success = connector.connect(device)
            val b = _binding ?: return@launch
            isConnected = success
            b.tvConnection.text = if (success) "● 연결됨" else "○ 미연결"
            if (success) {
                settings.deviceAddress = device.address
                rpiProtocol.startListening()
            }
            updateButtonStates()
        }
    }

    private fun startSession() {
        val mode = if (binding.rbDemo.isChecked) "DEMO" else "COLLECT"
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
        b.tvRoadType.text = status.roadType
        b.tvSpeed.text = "%.1f km/h".format(status.speed)
    }

    private fun handleDisconnected() {
        _binding?.let { b ->
            isConnected = false
            isSessionRunning = false
            timerJob?.cancel()
            b.tvConnection.text = "○ 미연결"
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
        val demoMode = binding.rbDemo.isChecked
        binding.rbCollect.isEnabled = isConnected && !isSessionRunning
        binding.rbDemo.isEnabled = isConnected && !isSessionRunning
        binding.btnSession.isEnabled = isConnected
        binding.btnSession.text = if (isSessionRunning) "정지" else "출발"
        binding.tvRoadType.visibility = if (demoMode) View.VISIBLE else View.GONE
        binding.tvSpeed.visibility = if (demoMode) View.VISIBLE else View.GONE
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
