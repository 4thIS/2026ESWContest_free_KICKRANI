package com.vibrasoft.kickboardapp.ui

import android.bluetooth.BluetoothDevice
import android.os.Bundle
import android.widget.Toast
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import com.vibrasoft.kickboardapp.MainActivity
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.data.SpeedUnit
import com.vibrasoft.kickboardapp.databinding.BottomsheetSettingsBinding
import kotlinx.coroutines.launch

class SettingsBottomSheet : BottomSheetDialogFragment() {
    private var _binding: BottomsheetSettingsBinding? = null
    private val binding get() = _binding!!

    private lateinit var settings: AppSettings

    private val devicePicker = BluetoothDevicePicker(
        fragment = this,
        connectorProvider = { (requireActivity() as MainActivity).bluetoothConnector },
        onDeviceSelected = { device -> connectTo(device) }
    )

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = BottomsheetSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        settings = AppSettings(requireContext())

        updateCurrentDeviceLabel()
        binding.btnReselect.setOnClickListener { devicePicker.requestPick() }

        when (settings.speedUnit) {
            SpeedUnit.KMH -> binding.rbUnitKmh.isChecked = true
            SpeedUnit.MPS -> binding.rbUnitMps.isChecked = true
        }
        binding.rgSpeedUnit.setOnCheckedChangeListener { _, checkedId ->
            settings.speedUnit =
                if (checkedId == binding.rbUnitMps.id) SpeedUnit.MPS else SpeedUnit.KMH
        }
    }

    private fun updateCurrentDeviceLabel() {
        val address = settings.deviceAddress
        _binding?.tvCurrentDevice?.text = address.ifEmpty { "선택된 기기 없음" }
    }

    private fun connectTo(device: BluetoothDevice) {
        viewLifecycleOwner.lifecycleScope.launch {
            val connector = (requireActivity() as MainActivity).bluetoothConnector
            val protocol = (requireActivity() as MainActivity).rpiProtocol
            val success = connector.connect(device)
            _binding ?: return@launch
            if (success) {
                settings.deviceAddress = device.address
                protocol.startListening()
                updateCurrentDeviceLabel()
            } else {
                // 이전에는 실패해도 아무 표시가 없어 원인을 알 수 없었다. 상세는 logcat "RpiLink".
                Toast.makeText(
                    requireContext(),
                    "연결 실패 — Pi에서 서버가 떠 있는지, 페어링이 유지되는지 확인",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
