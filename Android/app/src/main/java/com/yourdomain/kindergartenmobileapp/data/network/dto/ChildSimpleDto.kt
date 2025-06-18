package com.yourdomain.kindergartenmobileapp.data.network.dto
import com.google.gson.annotations.SerializedName

data class ChildSimpleDto(
    @SerializedName("id")
    val id: Int,

    @SerializedName("full_name")
    val fullName: String,


    @SerializedName("last_charge_amount")
    val lastChargeAmount: Double?,

    @SerializedName("last_charge_year")
    val lastChargeYear: Int?,

    @SerializedName("last_charge_month")
    val lastChargeMonth: Int?
)