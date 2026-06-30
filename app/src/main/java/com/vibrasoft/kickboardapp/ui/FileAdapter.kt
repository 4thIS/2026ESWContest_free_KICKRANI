package com.vibrasoft.kickboardapp.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.vibrasoft.kickboardapp.databinding.ItemFileBinding

class FileAdapter(
    private val files: MutableList<String>,
    private val onRename: (String) -> Unit,
    private val onMemo: (String) -> Unit
) : RecyclerView.Adapter<FileAdapter.ViewHolder>() {

    inner class ViewHolder(private val binding: ItemFileBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(fileName: String) {
            binding.tvFileName.text = fileName
            binding.btnRename.setOnClickListener { onRename(fileName) }
            binding.btnMemo.setOnClickListener { onMemo(fileName) }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemFileBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(files[position])
    }

    override fun getItemCount() = files.size

    fun updateFiles(newFiles: List<String>) {
        files.clear()
        files.addAll(newFiles)
        notifyDataSetChanged()
    }

    fun renameFile(oldName: String, newName: String) {
        val idx = files.indexOf(oldName)
        if (idx >= 0) {
            files[idx] = newName
            notifyItemChanged(idx)
        }
    }
}
