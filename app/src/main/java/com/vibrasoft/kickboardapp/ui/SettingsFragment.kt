package com.vibrasoft.kickboardapp.ui

import android.bluetooth.BluetoothDevice
import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.vibrasoft.kickboardapp.MainActivity
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.databinding.FragmentSettingsBinding
import kotlinx.coroutines.launch

class SettingsFragment : Fragment(R.layout.fragment_settings) {
    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!

    private lateinit var settings: AppSettings

    private val devicePicker = BluetoothDevicePicker(
        fragment = this,
        connectorProvider = { (requireActivity() as MainActivity).bluetoothConnector },
        onDeviceSelected = { device -> connectTo(device) }
    )

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentSettingsBinding.bind(view)
        settings = AppSettings(requireContext())

        updateCurrentDeviceLabel()
        binding.btnReselect.setOnClickListener { devicePicker.requestPick() }
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
