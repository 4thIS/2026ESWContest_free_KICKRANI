package com.vibrasoft.kickboardapp.ui

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.fragment.app.Fragment
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.data.AppSettings
import com.vibrasoft.kickboardapp.databinding.FragmentSettingsBinding

class SettingsFragment : Fragment(R.layout.fragment_settings) {
    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentSettingsBinding.bind(view)
        val settings = AppSettings(requireContext())

        // 저장된 값 불러오기
        binding.etSsid.setText(settings.ssid)
        binding.etPassword.setText(settings.password)
        binding.etIp.setText(settings.deviceIp)

        binding.btnSave.setOnClickListener {
            settings.ssid = binding.etSsid.text.toString().trim()
            settings.password = binding.etPassword.text.toString()
            settings.deviceIp = binding.etIp.text.toString().trim()
            Toast.makeText(requireContext(), "저장됨", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
