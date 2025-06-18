package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


enum class TransactionTypeDto(val value: String) {
    DEPOSIT("deposit"),
    WITHDRAWAL("withdrawal"),
    CORRECTION_PLUS("correction_plus"),
    CORRECTION_MINUS("correction_minus"),
    INITIAL_BALANCE("initial_balance");

    companion object {
        fun fromValue(value: String?): TransactionTypeDto? = values().find { it.value == value?.lowercase() }
    }
}


data class TransactionListItemDto(
    @SerializedName("id") val id: Int,
    @SerializedName("child_id") val childId: Int,
    @SerializedName("type") val typeRaw: String,
    @SerializedName("amount") val amount: Float,
    @SerializedName("balance_after") val balanceAfter: Float,
    @SerializedName("description") val description: String?,
    @SerializedName("transaction_date") val transactionDate: String,
    @SerializedName("created_by") val createdBy: Int?,
    @SerializedName("creator") val creator: UserSimpleDto?,
    @SerializedName("created_at") val createdAt: String
) {
    val type: TransactionTypeDto?
        get() = TransactionTypeDto.fromValue(typeRaw)
}