package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


data class ChildDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("full_name")
    val fullName: String,
    @SerializedName("group_id")
    val groupId: Int?

)

data class ChildDetailResponseDto(
    @SerializedName("id") val id: Int,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("birth_date") val birthDate: String,
    @SerializedName("address") val address: String?,
    @SerializedName("medical_info") val medicalInfo: String?,
    @SerializedName("group_id") val groupId: Int?,
    @SerializedName("group") val group: GroupSimpleDto?,
    @SerializedName("balance") val balance: Float,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)