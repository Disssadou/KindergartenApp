package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


enum class MealTypeDto(val value: String, val displayName: String) {
    BREAKFAST("breakfast", "Завтрак"),
    LUNCH("lunch", "Обед"),
    SNACK("snack", "Полдник");

    companion object {
        fun fromValue(value: String?): MealTypeDto? {
            return values().find { it.value == value }
        }
    }
}


data class MealMenuDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("date")
    val date: String,
    @SerializedName("meal_type")
    val mealTypeRaw: String,
    @SerializedName("description")
    val description: String,
    @SerializedName("created_at")
    val createdAt: String?,
    @SerializedName("updated_at")
    val updatedAt: String?

) {

    val mealType: MealTypeDto?
        get() = MealTypeDto.fromValue(mealTypeRaw)
}