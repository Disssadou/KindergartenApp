package com.yourdomain.kindergartenmobileapp.ui.screens.teacher.attendance

import androidx.lifecycle.SavedStateHandle
import timber.log.Timber
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.AbsenceTypeDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.AttendanceRecordDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.BulkAttendanceCreateDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.BulkAttendanceItemDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject


data class ChildAttendanceDisplayItem(
    val child: ChildDto,
    var uiIsPresent: Boolean,
    var uiAbsenceType: AbsenceTypeDto?,
    var uiAbsenceReason: String?,
    val serverIsPresent: Boolean,
    val serverAbsenceType: AbsenceTypeDto?,
    val serverAbsenceReason: String?,

    val hasPendingChanges: Boolean = false
)


sealed interface AttendanceMarkingUiState {
    data object Loading : AttendanceMarkingUiState
    data class Success(
        val items: List<ChildAttendanceDisplayItem>,
        val date: LocalDate,
        val groupName: String
    ) : AttendanceMarkingUiState
    data class Error(val message: String, val date: LocalDate, val groupName: String) : AttendanceMarkingUiState
}

@HiltViewModel
class AttendanceMarkingViewModel @Inject constructor(
    private val authApiService: AuthApiService,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val groupId: Int = checkNotNull(savedStateHandle["groupId"])
    private val groupName: String = checkNotNull(savedStateHandle["groupName"])

    private val _selectedDate = MutableStateFlow(LocalDate.now())
    val selectedDate: StateFlow<LocalDate> = _selectedDate.asStateFlow()

    private val _uiState = MutableStateFlow<AttendanceMarkingUiState>(AttendanceMarkingUiState.Loading)
    val uiState: StateFlow<AttendanceMarkingUiState> = _uiState.asStateFlow()


    private var currentDisplayItems = mutableListOf<ChildAttendanceDisplayItem>()

    init {

        viewModelScope.launch {
            selectedDate.collect { date ->
                loadAttendanceData(date)
            }
        }
    }

    fun onDateSelected(date: LocalDate) {
        _selectedDate.value = date

    }

    fun loadAttendanceData(date: LocalDate) {
        _uiState.value = AttendanceMarkingUiState.Loading
        currentDisplayItems.clear()
        viewModelScope.launch {
            val dateStr = date.format(DateTimeFormatter.ISO_LOCAL_DATE)
            var errorMessage: String? = null
            var errorCode: Int? = null

            try {
                val dateStr = date.format(DateTimeFormatter.ISO_LOCAL_DATE)


                val childrenResponse = authApiService.getChildrenForGroup(groupId = groupId)
                if (!childrenResponse.isSuccessful || childrenResponse.body() == null) {
                    errorCode = childrenResponse.code()
                    errorMessage = childrenResponse.errorBody()?.string() ?: "Не удалось загрузить список детей ($errorCode)"
                    if (errorCode == 403) {
                        errorMessage = "Доступ к детям этой группы запрещен."
                    }
                    _uiState.value = AttendanceMarkingUiState.Error(errorMessage!!, date, groupName)
                    return@launch
                }
                val children = childrenResponse.body()!!

                if (children.isEmpty()) {
                    _uiState.value = AttendanceMarkingUiState.Success(emptyList(), date, groupName)
                    return@launch
                }


                val attendanceResponse = authApiService.getAttendanceRecords(groupId = groupId, date = dateStr)
                val existingRecordsMap = if (attendanceResponse.isSuccessful && attendanceResponse.body() != null) {
                    attendanceResponse.body()!!.associateBy { it.childId }
                } else {

                    Timber.w("Failed to load existing attendance records for group $groupId on $dateStr. Code: ${attendanceResponse.code()}")
                    mapOf<Int, AttendanceRecordDto>()
                }


                currentDisplayItems.addAll(children.map { child ->
                    val record = existingRecordsMap[child.id]
                    ChildAttendanceDisplayItem(
                        child = child,
                        uiIsPresent = record?.present ?: false,
                        uiAbsenceType = record?.absenceType?.let { typeVal -> AbsenceTypeDto.values().find { it.value == typeVal } },
                        uiAbsenceReason = record?.absenceReason,
                        serverIsPresent = record?.present ?: false,
                        serverAbsenceType = record?.absenceType?.let { typeVal -> AbsenceTypeDto.values().find { it.value == typeVal } },
                        serverAbsenceReason = record?.absenceReason,
                        hasPendingChanges = false
                    )
                })

                _uiState.value = AttendanceMarkingUiState.Success(currentDisplayItems.toList(), date, groupName)

            } catch (e: Exception) {
                Timber.e("Exception in loadAttendanceData", e)
                _uiState.value = AttendanceMarkingUiState.Error(
                    e.message ?: "Произошла неизвестная ошибка при загрузке данных посещаемости",
                    date, groupName
                )
            }
        }
    }

    fun updateChildAttendance(childId: Int, isPresent: Boolean, type: AbsenceTypeDto?, reason: String?) {
        val itemIndex = currentDisplayItems.indexOfFirst { it.child.id == childId }
        if (itemIndex != -1) {
            val oldItem = currentDisplayItems[itemIndex]
            val newItem = oldItem.copy(
                uiIsPresent = isPresent,
                uiAbsenceType = if (isPresent) null else type,
                uiAbsenceReason = if (isPresent) null else reason?.ifBlank { null }
            )

            val changed = newItem.uiIsPresent != newItem.serverIsPresent ||
                    newItem.uiAbsenceType != newItem.serverAbsenceType ||
                    newItem.uiAbsenceReason != newItem.serverAbsenceReason

            currentDisplayItems[itemIndex] = newItem.copy(hasPendingChanges = changed)

            _uiState.update { currentState ->
                if (currentState is AttendanceMarkingUiState.Success) {
                    currentState.copy(items = currentDisplayItems.toList())
                } else { currentState }
            }
        }
    }

    fun saveAttendance() {
        if (currentDisplayItems.isEmpty()) {

            val currentGroupName = (_uiState.value as? AttendanceMarkingUiState.Success)?.groupName ?: groupName
            _uiState.value = AttendanceMarkingUiState.Error("Нет данных для сохранения", selectedDate.value, currentGroupName)
            return
        }


        val previousSuccessStateData = (_uiState.value as? AttendanceMarkingUiState.Success)?.items
            ?: currentDisplayItems.toList()

        _uiState.value = AttendanceMarkingUiState.Loading
        Timber.d("SaveAttendance: State set to Loading")

        viewModelScope.launch {
            try {
                val bulkItems = currentDisplayItems.map { displayItem ->
                    BulkAttendanceItemDto(
                        childId = displayItem.child.id,
                        present = displayItem.uiIsPresent,
                        absenceReason = if (displayItem.uiIsPresent) null else displayItem.uiAbsenceReason,
                        absenceType = if (displayItem.uiIsPresent) null else displayItem.uiAbsenceType?.value
                    )
                }
                val bulkCreateDto = BulkAttendanceCreateDto(
                    groupId = groupId,
                    date = selectedDate.value.format(DateTimeFormatter.ISO_LOCAL_DATE),
                    attendanceList = bulkItems
                )
                Timber.d("SaveAttendance: Sending bulk request: $bulkCreateDto")
                val response = authApiService.postBulkAttendance(bulkCreateDto)
                Timber.d("SaveAttendance: Received response code: ${response.code()}")

                if (response.isSuccessful && response.body() != null) {
                    val updatedRecordsFromServer = response.body()!!
                    Timber.d("SaveAttendance: Success. Server response: $updatedRecordsFromServer")


                    val newDisplayItems = currentDisplayItems.map { displayItem ->
                        val serverRecord = updatedRecordsFromServer.find { it.childId == displayItem.child.id }
                        if (serverRecord != null) {
                            displayItem.copy(
                                uiIsPresent = serverRecord.present,
                                uiAbsenceType = serverRecord.absenceType?.let { typeVal -> AbsenceTypeDto.values().find { it.value == typeVal } },
                                uiAbsenceReason = serverRecord.absenceReason,
                                serverIsPresent = serverRecord.present,
                                serverAbsenceType = serverRecord.absenceType?.let { typeVal -> AbsenceTypeDto.values().find { it.value == typeVal } },
                                serverAbsenceReason = serverRecord.absenceReason,
                                hasPendingChanges = false
                            )
                        } else {

                            displayItem.copy(hasPendingChanges = true)

                        }
                    }
                    currentDisplayItems.clear()
                    currentDisplayItems.addAll(newDisplayItems.filterNotNull())


                    _uiState.value = AttendanceMarkingUiState.Success(
                        items = currentDisplayItems.toList(),
                        date = selectedDate.value,
                        groupName = groupName
                    )
                    Timber.d("SaveAttendance: State set to Success with ${currentDisplayItems.size} items.")
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Ошибка сохранения (${response.code()})"
                    Timber.e("SaveAttendance: Error in response. Msg: $errorMsg")

                    _uiState.value = AttendanceMarkingUiState.Error(errorMsg, selectedDate.value, groupName)
                    
                }
            } catch (e: Exception) {
                Timber.e(e, "SaveAttendance: Exception during save.")
                _uiState.value = AttendanceMarkingUiState.Error(
                    e.message ?: "Ошибка сохранения посещаемости",
                    selectedDate.value, groupName
                )
            }
        }
    }
}