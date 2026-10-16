package com.yarbis.client.model

import com.google.gson.annotations.SerializedName

/**
 * Tipo principal de acción devuelta por Yarbis Backend.
 */
enum class ActionType {
    @SerializedName("device_control")
    DEVICE_CONTROL,

    @SerializedName("conversational_query")
    CONVERSATIONAL_QUERY
}

/**
 * Contrato estándar de respuesta de la API Yarbis para Kotlin / Android.
 */
data class YarbisResponse(
    @SerializedName("action_type")
    val actionType: ActionType,

    @SerializedName("command")
    val command: String? = null,

    @SerializedName("parameters")
    val parameters: Map<String, Any?> = emptyMap(),

    @SerializedName("text_response")
    val textResponse: String,

    @SerializedName("audio_url")
    val audioUrl: String? = null,

    @SerializedName("audio_base64")
    val audioBase64: String? = null,

    @SerializedName("transcription")
    val transcription: String? = null,

    @SerializedName("session_id")
    val sessionId: String? = null
)
