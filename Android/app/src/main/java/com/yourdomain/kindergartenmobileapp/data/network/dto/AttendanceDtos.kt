package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName


enum class AbsenceTypeDto(val value: String) {
    SICK_LEAVE("sick_leave"),
    VACATION("vacation"),
    OTHER("other")
}


data class AttendanceRecordDto(
    @SerializedName("id")
    val id: Int?,
    @SerializedName("child_id")
    val childId: Int,
    @SerializedName("date")
    val date: String,
    @SerializedName("present")
    val present: Boolean,
    @SerializedName("absence_reason")
    val absenceReason: String?,
    @SerializedName("absence_type")
    val absenceType: String?
)


data class BulkAttendanceItemDto(
    @SerializedName("child_id")
    val childId: Int,
    @SerializedName("present")
    val present: Boolean,
    @SerializedName("absence_reason")
    val absenceReason: String?,
    @SerializedName("absence_type")
    val absenceType: String?
)


data class BulkAttendanceCreateDto(
    @SerializedName("group_id")
    val groupId: Int,
    @SerializedName("date")
    val date: String,
    @SerializedName("attendance_list")
    val attendanceList: List<BulkAttendanceItemDto>
)

