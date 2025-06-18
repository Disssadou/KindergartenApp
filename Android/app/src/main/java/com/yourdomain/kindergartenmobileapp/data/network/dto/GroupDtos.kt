package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


data class TeacherSimpleDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("username")
    val username: String,
    @SerializedName("full_name")
    val fullName: String
)


data class GroupDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("name")
    val name: String,
    @SerializedName("description")
    val description: String?,
    @SerializedName("teacher_id")
    val teacherId: Int?,
    @SerializedName("teacher")
    val teacher: TeacherSimpleDto?,
    @SerializedName("age_min")
    val ageMin: Int?,
    @SerializedName("age_max")
    val ageMax: Int?,
    @SerializedName("capacity")
    val capacity: Int?,
    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String

)

data class GroupSimpleDto(
     @SerializedName("id") val id: Int,
     @SerializedName("name") val name: String
)