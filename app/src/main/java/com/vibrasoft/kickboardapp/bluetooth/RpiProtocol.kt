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
    data class Status(
        val speed: Float,
        val distance: Float? = null,
        val vibration: Float? = null,
        val roadType: String? = null
    ) : RpiMessage()
    data class Files(val files: List<String>) : RpiMessage()
    data class Error(val cmd: String, val message: String) : RpiMessage()
}

class RpiProtocol(private val connector: BluetoothConnector) {
    // Dispatchers.Main: readLine()의 실제 블로킹 호출은 connector 내부에서 IO로 전환되고,
    // 콜백 디스패치는 여기서 Main으로 돌아와 UI를 바로 건드릴 수 있게 한다.
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var listenJob: Job? = null

    private val ackListeners = mutableListOf<(String, Boolean) -> Unit>()
    private val statusListeners = mutableListOf<(RpiMessage.Status) -> Unit>()
    private val filesListeners = mutableListOf<(List<String>) -> Unit>()
    private val errorListeners = mutableListOf<(String, String) -> Unit>()
    private val disconnectedListeners = mutableListOf<() -> Unit>()

    fun addAckListener(listener: (String, Boolean) -> Unit) { ackListeners.add(listener) }
    fun removeAckListener(listener: (String, Boolean) -> Unit) { ackListeners.remove(listener) }

    fun addStatusListener(listener: (RpiMessage.Status) -> Unit) { statusListeners.add(listener) }
    fun removeStatusListener(listener: (RpiMessage.Status) -> Unit) { statusListeners.remove(listener) }

    fun addFilesListener(listener: (List<String>) -> Unit) { filesListeners.add(listener) }
    fun removeFilesListener(listener: (List<String>) -> Unit) { filesListeners.remove(listener) }

    fun addErrorListener(listener: (String, String) -> Unit) { errorListeners.add(listener) }
    fun removeErrorListener(listener: (String, String) -> Unit) { errorListeners.remove(listener) }

    fun addDisconnectedListener(listener: () -> Unit) { disconnectedListeners.add(listener) }
    fun removeDisconnectedListener(listener: () -> Unit) { disconnectedListeners.remove(listener) }

    fun startListening() {
        listenJob?.cancel()
        listenJob = scope.launch {
            while (isActive) {
                val line = connector.readLine()
                if (line == null) {
                    disconnectedListeners.toList().forEach { it.invoke() }
                    break
                }
                when (val message = parseMessage(line)) {
                    is RpiMessage.Ack -> ackListeners.toList().forEach { it(message.cmd, message.ok) }
                    is RpiMessage.Status -> statusListeners.toList().forEach { it(message) }
                    is RpiMessage.Files -> filesListeners.toList().forEach { it(message.files) }
                    is RpiMessage.Error -> errorListeners.toList().forEach { it(message.cmd, message.message) }
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
                        speed = json.getDouble("speed").toFloat(),
                        distance = if (json.has("distance")) json.getDouble("distance").toFloat() else null,
                        vibration = if (json.has("vibration")) json.getDouble("vibration").toFloat() else null,
                        roadType = if (json.has("roadType")) json.getString("roadType") else null
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
