package com.vibrasoft.kickboardapp.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.navigation.fragment.findNavController
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.databinding.FragmentMainBinding
import com.vibrasoft.kickboardapp.gps.GpsLogger
import com.vibrasoft.kickboardapp.network.DeviceApi
import com.vibrasoft.kickboardapp.wifi.WifiConnector
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainFragment : Fragment(R.layout.fragment_main) {
    private var _binding: FragmentMainBinding? = null
    private val binding get() = _binding!!

    private lateinit var settings: AppSettings
    private lateinit var api: DeviceApi
    private lateinit var gpsLogger: GpsLogger
    private lateinit var wifiConnector: WifiConnector

    private var isConnected = false
    private var isSessionRunning = false
    private var timerJob: Job? = null
    private var elapsedSeconds = 0L

    private val locationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        if (grants.values.all { it }) startSession()
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentMainBinding.bind(view)
        settings = AppSettings(requireContext())
        api = DeviceApi(settings.deviceIp)
        gpsLogger = GpsLogger(requireContext())
        wifiConnector = WifiConnector(requireContext())

        gpsLogger.onSpeedUpdate = { speed ->
            _binding?.tvSpeed?.text = "%.1f km/h".format(speed)
        }

        binding.btnConnect.setOnClickListener { connectWifi() }
        binding.btnSync.setOnClickListener { syncTime() }
        binding.btnSession.setOnClickListener {
            if (isSessionRunning) stopSession() else checkPermissionAndStart()
        }

        updateButtonStates()
    }

    private fun connectWifi() {
        binding.tvConnection.text = "연결 중..."
        wifiConnector.connect(settings.ssid, settings.password) { success ->
            requireActivity().runOnUiThread {
                val b = _binding ?: return@runOnUiThread
                isConnected = success
                b.tvConnection.text = if (success) "● 연결됨" else "○ 미연결"
                updateButtonStates()
            }
        }
    }

    private fun syncTime() {
        lifecycleScope.launch {
            api.sync(System.currentTimeMillis())
        }
    }

    private fun checkPermissionAndStart() {
        val perms = arrayOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (perms.all { ContextCompat.checkSelfPermission(requireContext(), it) == PackageManager.PERMISSION_GRANTED }) {
            startSession()
        } else {
            locationPermissionLauncher.launch(perms)
        }
    }

    private fun startSession() {
        lifecycleScope.launch {
            api.sync(System.currentTimeMillis())
            api.start()
            gpsLogger.start()
            isSessionRunning = true
            elapsedSeconds = 0L
            startTimer()
            updateButtonStates()
        }
    }

    private fun stopSession() {
        lifecycleScope.launch {
            api.stop()
            val points = gpsLogger.stop()
            api.sendSpeedLog(points)
            isSessionRunning = false
            timerJob?.cancel()
            updateButtonStates()
            findNavController().navigate(R.id.fileFragment)
        }
    }

    private fun startTimer() {
        timerJob?.cancel()
        timerJob = lifecycleScope.launch {
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
        binding.btnSync.isEnabled = isConnected && !isSessionRunning
        binding.btnSession.isEnabled = isConnected
        binding.btnSession.text = if (isSessionRunning) "세션 종료" else "세션 시작"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        timerJob?.cancel()
        gpsLogger.onSpeedUpdate = null
        _binding = null
    }
}
