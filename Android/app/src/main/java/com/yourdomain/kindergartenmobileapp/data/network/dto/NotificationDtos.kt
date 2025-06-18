package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


enum class NotificationAudienceDto(val value: String, val displayName: String) {
    ALL("all", "Всем"),
    PARENTS("parents", "Родителям"),
    TEACHERS("teachers", "Воспитателям");


    companion object {
        fun fromValue(value: String?): NotificationAudienceDto? {
            return values().find { it.value.equals(value, ignoreCase = true) }
        }
    }
}


data class NotificationDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("title")
    val title: String,
    @SerializedName("content")
    val content: String,
    @SerializedName("author_id")
    val authorId: Int?,


    @SerializedName("is_event")
    val isEvent: Boolean,
    @SerializedName("event_date")
    val eventDate: String?,

    @SerializedName("audience")
    val audienceRaw: String,

    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String
) {

    val audience: NotificationAudienceDto?
        get() = audienceRaw?.let { rawVal ->
            NotificationAudienceDto.values().find { it.value == rawVal.lowercase() }
        }
}

