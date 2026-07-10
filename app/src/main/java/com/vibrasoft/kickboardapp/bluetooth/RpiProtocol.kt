package com.vibrasoft.kickboardapp.bluetooth

import org.json.JSONException
import org.json.JSONObject

sealed class RpiMessage {
    data class Ack(val cmd: String, val ok: Boolean) : RpiMessage()
    data class Status(val speed: Float, val roadType: String) : RpiMessage()
    data class Files(val files: List<String>) : RpiMessage()
    data class Error(val cmd: String, val message: String) : RpiMessage()
}

class RpiProtocol {

    companion object {
        private fun escape(s: String): String =
            s.replace("\\", "\\\\").replace("\"", "\\\"")

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
