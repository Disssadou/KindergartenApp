package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName

data class UserSimpleDto(
    @SerializedName("id") val id: Int,
    @SerializedName("username") val username: String,
    @SerializedName("full_name") val fullName: String
)

