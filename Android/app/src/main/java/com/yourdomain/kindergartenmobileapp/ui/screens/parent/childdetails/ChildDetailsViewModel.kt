
package com.yourdomain.kindergartenmobileapp.ui.screens.parent.childdetails

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService

import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildDetailResponseDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.MealMenuDto

import com.yourdomain.kindergartenmobileapp.data.network.dto.MonthlyChargeDto
import dagger.hilt.android.lifecycle.HiltViewModel

import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import timber.log.Timber
import java.time.LocalDate

import java.time.format.DateTimeFormatter
import javax.inject.Inject


sealed interface ChildInfoUiState {
    data object Loading : ChildInfoUiState
    data class Success(val childDetails: ChildDetailResponseDto) : ChildInfoUiState
    data class Error(val message: String) : ChildInfoUiState
}


sealed interface AttendanceUiState {
    data object Loading : AttendanceUiState
    data class Success(
        val records: Map<LocalDate, Any>,
        val holidays: Set<LocalDate>,
        val forMonth: java.time.YearMonth
    ) : AttendanceUiState
    data class Error(val message: String, val forMonth: java.time.YearMonth) : AttendanceUiState
    data object Idle : AttendanceUiState
}


sealed interface MonthlyChargesUiState {
    data object Loading : MonthlyChargesUiState
    data class Success(val charges: List<MonthlyChargeDto>) : MonthlyChargesUiState
    data class Error(val message: String) : MonthlyChargesUiState

}

sealed interface ChildMenuUiState {
    data object Loading : ChildMenuUiState
    data class Success(val menuItems: List<MealMenuDto>, val forDate: LocalDate) : ChildMenuUiState
    data class Error(val message: String, val forDate: LocalDate) : ChildMenuUiState
    data object Idle : ChildMenuUiState
}

@HiltViewModel
class ChildDetailsViewModel @Inject constructor(
    private val authApiService: AuthApiService,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val childId: Int = checkNotNull(savedStateHandle["childId"]) { "childId not found in SavedStateHandle" }

    private val _childInfoState = MutableStateFlow<ChildInfoUiState>(ChildInfoUiState.Loading)
    val childInfoState: StateFlow<ChildInfoUiState> = _childInfoState.asStateFlow()


    private val _monthlyChargesState = MutableStateFlow<MonthlyChargesUiState>(MonthlyChargesUiState.Loading)
    val monthlyChargesState: StateFlow<MonthlyChargesUiState> = _monthlyChargesState.asStateFlow()

    private val _menuState = MutableStateFlow<ChildMenuUiState>(ChildMenuUiState.Idle)
    val menuState: StateFlow<ChildMenuUiState> = _menuState.asStateFlow()
    val currentSelectedDateForMenu = MutableStateFlow(LocalDate.now())

    init {
        Timber.d("ChildDetailsViewModel init for childId: $childId")
        loadChildDetails()
        loadMonthlyCharges()
    }

    fun loadChildDetails() {
        _childInfoState.value = ChildInfoUiState.Loading
        viewModelScope.launch {
            try {
                val response = authApiService.getChildDetails(childId)
                if (response.isSuccessful && response.body() != null) {
                    _childInfoState.value = ChildInfoUiState.Success(response.body()!!)
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Не удалось загрузить данные ребенка (${response.code()})"
                    Timber.e("Failed to load child details for $childId: $errorMsg")
                    _childInfoState.value = ChildInfoUiState.Error(errorMsg)
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception loading child details for $childId")
                _childInfoState.value = ChildInfoUiState.Error(e.message ?: "Произошла неизвестная ошибка")
            }
        }
    }


    fun loadMonthlyCharges(year: Int? = null) {
        _monthlyChargesState.value = MonthlyChargesUiState.Loading
        viewModelScope.launch {
            try {

                val response = authApiService.getMonthlyChargesForChild(childId = childId, year = year)
                if (response.isSuccessful && response.body() != null) {
                    _monthlyChargesState.value = MonthlyChargesUiState.Success(response.body()!!)
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Не удалось загрузить историю начислений (${response.code()})"
                    Timber.e("Failed to load monthly charges for $childId: $errorMsg")
                    _monthlyChargesState.value = MonthlyChargesUiState.Error(errorMsg)
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception loading monthly charges for $childId")
                _monthlyChargesState.value = MonthlyChargesUiState.Error(e.message ?: "Произошла неизвестная ошибка")
            }
        }
    }

    fun loadMenuForDate(date: LocalDate) {
        _menuState.value = ChildMenuUiState.Loading
        viewModelScope.launch {
            try {
                val dateStr = date.format(DateTimeFormatter.ISO_LOCAL_DATE)
                val response = authApiService.getMealMenus(startDate = dateStr, endDate = dateStr)
                if (response.isSuccessful && response.body() != null) {
                    _menuState.value = ChildMenuUiState.Success(response.body()!!, date)
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Не удалось загрузить меню (${response.code()})"
                    Timber.e("Failed to load menu for $dateStr: $errorMsg")
                    _menuState.value = ChildMenuUiState.Error(errorMsg, date)
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception loading menu for $date")
                _menuState.value = ChildMenuUiState.Error(e.message ?: "Произошла неизвестная ошибка", date)
            }
        }
    }
    fun selectMenuDate(date: LocalDate) {
        currentSelectedDateForMenu.value = date
    }
}