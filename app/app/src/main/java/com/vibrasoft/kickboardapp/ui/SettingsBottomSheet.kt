package com.vibrasoft.kickboardapp.ui

import android.bluetooth.BluetoothDevice
import android.os.Bundle
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
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
