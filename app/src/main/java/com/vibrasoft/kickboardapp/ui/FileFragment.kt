package com.vibrasoft.kickboardapp.ui

import android.os.Bundle
import android.view.View
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.vibrasoft.kickboardapp.MainActivity
import com.vibrasoft.kickboardapp.R
import com.vibrasoft.kickboardapp.bluetooth.RpiProtocol
import com.vibrasoft.kickboardapp.databinding.FragmentFileBinding
import kotlinx.coroutines.launch

class FileFragment : Fragment(R.layout.fragment_file) {
    private var _binding: FragmentFileBinding? = null
    private val binding get() = _binding!!

    private lateinit var rpiProtocol: RpiProtocol
    private lateinit var adapter: FileAdapter

    private val roadTypes = listOf("아스팔트", "보도블럭", "콘크리트", "비포장", "기타")
    private val roadConditions = listOf("정상", "불량")
    private var pendingRename: Pair<String, String>? = null

    private val onErrorCallback: (String, String) -> Unit = { cmd, message ->
        handleError(cmd, message)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentFileBinding.bind(view)
        rpiProtocol = (requireActivity() as MainActivity).rpiProtocol

        adapter = FileAdapter(
            mutableListOf(),
            onRename = { fileName -> showRoadTypeDialog(fileName) },
            onMemo = { fileName -> showMemoDialog(fileName) }
        )
        binding.rvFiles.layoutManager = LinearLayoutManager(requireContext())
        binding.rvFiles.adapter = adapter

        rpiProtocol.onFiles = { files ->
            _binding?.let { adapter.updateFiles(files) }
        }
        rpiProtocol.onAck = { cmd, ok -> handleAck(cmd, ok) }
        rpiProtocol.onError = onErrorCallback

        binding.btnRefresh.setOnClickListener { loadFiles() }
        loadFiles()
    }

    private fun loadFiles() {
        viewLifecycleOwner.lifecycleScope.launch {
            rpiProtocol.sendCommand(RpiProtocol.buildListFilesCommand())
        }
    }

    // 1단계: 노면 종류 선택
    private fun showRoadTypeDialog(fileName: String) {
        var selectedType = roadTypes[0]

        val dialog = AlertDialog.Builder(requireContext())
            .setTitle("노면 종류 선택")
            .setSingleChoiceItems(roadTypes.toTypedArray(), 0) { _, which ->
                selectedType = roadTypes[which]
            }
            .setPositiveButton("다음") { _, _ ->
                if (selectedType == "기타") {
                    showCustomTypeDialog(fileName)
                } else {
                    showRoadConditionDialog(fileName, selectedType)
                }
            }
            .setNegativeButton("취소", null)
            .create()
        dialog.show()
    }

    // 기타 선택 시 직접 입력
    private fun showCustomTypeDialog(fileName: String) {
        val input = EditText(requireContext()).apply { hint = "노면 종류 입력" }
        AlertDialog.Builder(requireContext())
            .setTitle("노면 종류 직접 입력")
            .setView(input)
            .setPositiveButton("다음") { _, _ ->
                val custom = input.text.toString().trim()
                if (custom.isNotEmpty()) showRoadConditionDialog(fileName, custom)
            }
            .setNegativeButton("취소", null)
            .show()
    }

    // 2단계: 노면 상태 선택
    private fun showRoadConditionDialog(fileName: String, roadType: String) {
        var selectedCondition = roadConditions[0]
        AlertDialog.Builder(requireContext())
            .setTitle("노면 상태 선택")
            .setSingleChoiceItems(roadConditions.toTypedArray(), 0) { _, which ->
                selectedCondition = roadConditions[which]
            }
            .setPositiveButton("확인") { _, _ ->
                renameFile(fileName, roadType, selectedCondition)
            }
            .setNegativeButton("뒤로") { _, _ ->
                showRoadTypeDialog(fileName)
            }
            .show()
    }

    private fun renameFile(oldName: String, roadType: String, condition: String) {
        val newName = RpiProtocol.buildNewFileName(oldName, roadType, condition)
        pendingRename = oldName to newName
        viewLifecycleOwner.lifecycleScope.launch {
            val sent = rpiProtocol.sendCommand(RpiProtocol.buildRenameCommand(oldName, newName))
            if (!sent) {
                pendingRename = null
                _binding?.let {
                    Toast.makeText(requireContext(), "이름 변경 요청 전송 실패", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun handleAck(cmd: String, ok: Boolean) {
        if (cmd != "RENAME") return
        val (oldName, newName) = pendingRename ?: return
        pendingRename = null
        _binding?.let {
            if (ok) {
                adapter.renameFile(oldName, newName)
            } else {
                Toast.makeText(requireContext(), "이름 변경 실패: $oldName", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun handleError(cmd: String, message: String) {
        _binding?.let {
            Toast.makeText(requireContext(), "$cmd 실패: $message", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showMemoDialog(fileName: String) {
        val input = EditText(requireContext()).apply { hint = "메모 입력" }
        AlertDialog.Builder(requireContext())
            .setTitle(fileName)
            .setView(input)
            .setPositiveButton("추가") { _, _ ->
                val memo = input.text.toString().trim()
                if (memo.isNotEmpty()) {
                    viewLifecycleOwner.lifecycleScope.launch {
                        rpiProtocol.sendCommand(RpiProtocol.buildMemoCommand(fileName, memo))
                    }
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        rpiProtocol.onFiles = null
        rpiProtocol.onAck = null
        if (rpiProtocol.onError === onErrorCallback) rpiProtocol.onError = null
        _binding = null
    }
}
