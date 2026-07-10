package com.vibrasoft.kickboardapp.bluetooth

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONException
import org.json.JSONObject

sealed class RpiMessage {
    data class Ack(val cmd: String, val ok: Boolean) : RpiMessage()
    data class Status(val speed: Float, val roadType: String) : RpiMessage()
    data class Files(val files: List<String>) : RpiMessage()
    data class Error(val cmd: String, val message: String) : RpiMessage()
}

class RpiProtocol(private val connector: BluetoothConnector) {
    // Dispatchers.Main: readLine()의 실제 블로킹 호출은 connector 내부에서 IO로 전환되고,
    // 콜백 디스패치는 여기서 Main으로 돌아와 UI를 바로 건드릴 수 있게 한다.
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var listenJob: Job? = null

    var onAck: ((String, Boolean) -> Unit)? = null
    var onStatus: ((RpiMessage.Status) -> Unit)? = null
    var onFiles: ((List<String>) -> Unit)? = null
    var onError: ((String, String) -> Unit)? = null
    var onDisconnected: (() -> Unit)? = null

    fun startListening() {
        listenJob?.cancel()
        listenJob = scope.launch {
            while (isActive) {
                val line = connector.readLine()
                if (line == null) {
                    onDisconnected?.invoke()
                    break
                }
                when (val message = parseMessage(line)) {
                    is RpiMessage.Ack -> onAck?.invoke(message.cmd, message.ok)
                    is RpiMessage.Status -> onStatus?.invoke(message)
                    is RpiMessage.Files -> onFiles?.invoke(message.files)
                    is RpiMessage.Error -> onError?.invoke(message.cmd, message.message)
                    null -> {}
                }
            }
        }
    }

    fun stopListening() {
        listenJob?.cancel()
    }

    suspend fun sendCommand(command: String): Boolean = connector.send(command)

    companion object {
        private fun escape(s: String): String =
            s.replace("\\", "\\\\")
             .replace("\"", "\\\"")
             .replace("\n", "\\n")
             .replace("\r", "\\r")

        fun buildSetModeCommand(mode: String): String =
            """{"cmd":"SET_MODE","mode":"${escape(mode)}"}"""

        fun buildStartCommand(): String = """{"cmd":"START"}"""

        fun buildStopCommand(): String = """{"cmd":"STOP"}"""

        fun buildListFilesCommand(): String = """{"cmd":"LIST_FILES"}"""

        fun buildRenameCommand(old: String, new: String): String =
            """{"cmd":"RENAME","old":"${escape(old)}","new":"${escape(new)}"}"""

        fun buildMemoCommand(file: String, memo: String): String =
            """{"cmd":"MEMO","file":"${escape(file)}","memo":"${escape(memo)}"}"""

        fun buildNewFileName(original: String, roadType: String, condition: String): String {
            val base = original.removeSuffix(".csv")
            return "${base}_${roadType}_${condition}.csv"
        }

        fun parseMessage(line: String): RpiMessage? {
            return try {
                val json = JSONObject(line)
                when (json.optString("type")) {
                    "ACK" -> RpiMessage.Ack(json.getString("cmd"), json.getBoolean("ok"))
                    "STATUS" -> RpiMessage.Status(
                        json.getDouble("speed").toFloat(),
                        json.getString("roadType")
                    )
                    "FILES" -> {
                        val arr = json.getJSONArray("files")
                        RpiMessage.Files((0 until arr.length()).map { arr.getString(it) })
                    }
                    "ERROR" -> RpiMessage.Error(json.optString("cmd"), json.optString("message"))
                    else -> null
                }
            } catch (e: JSONException) {
                null
            }
        }
    }
}
