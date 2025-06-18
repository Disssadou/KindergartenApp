package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName



data class MonthlyChargeDto(
    @SerializedName("id")
    val id: Int,

    @SerializedName("child_id")
    val childId: Int,

    @SerializedName("year")
    val year: Int,

    @SerializedName("month")
    val month: Int,

    @SerializedName("amount_due")
    val amountDue: Double,

    @SerializedName("calculation_details")
    val calculationDetails: String?,

    @SerializedName("calculated_at")
    val calculatedAt: String
)