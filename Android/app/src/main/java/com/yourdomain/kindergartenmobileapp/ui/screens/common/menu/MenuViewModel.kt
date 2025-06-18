package com.yourdomain.kindergartenmobileapp.ui.screens.common.menu

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.MealMenuDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.MealTypeDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject


sealed interface MenuUiState {
    data object Loading : MenuUiState

    data class Success(val menuByMealType: Map<MealTypeDto, List<MealMenuDto>>, val date: LocalDate) : MenuUiState
    data class Error(val message: String, val date: LocalDate) : MenuUiState
    data class Empty(val date: LocalDate) : MenuUiState
}

@HiltViewModel
class MenuViewModel @Inject constructor(
    private val authApiService: AuthApiService
) : ViewModel() {

    private val _selectedDate = MutableStateFlow(LocalDate.now())
    val selectedDate: StateFlow<LocalDate> = _selectedDate.asStateFlow()

    private val _uiState = MutableStateFlow<MenuUiState>(MenuUiState.Loading)
    val uiState: StateFlow<MenuUiState> = _uiState.asStateFlow()

    init {

        viewModelScope.launch {
            selectedDate.collect { date ->
                loadMenuForDate(date)
            }
        }
    }

    fun onDateSelected(date: LocalDate) {
        _selectedDate.value = date

    }

    fun loadMenuForDate(date: LocalDate = _selectedDate.value) {
        _uiState.value = MenuUiState.Loading
        viewModelScope.launch {
            try {
                val dateStr = date.format(DateTimeFormatter.ISO_LOCAL_DATE)
                val response = authApiService.getMealMenus(startDate = dateStr, endDate = dateStr)

                if (response.isSuccessful && response.body() != null) {
                    val menus = response.body()!!
                    if (menus.isEmpty()) {
                        _uiState.value = MenuUiState.Empty(date)
                    } else {

                        val menuByMealType = menus
                            .filter { it.mealType != null }
                            .groupBy { it.mealType!! }
                            .toSortedMap(compareBy { it?.ordinal })
                        _uiState.value = MenuUiState.Success(menuByMealType, date)
                    }
                } else {
                    _uiState.value = MenuUiState.Error(
                        response.errorBody()?.string() ?: "Не удалось загрузить меню (${response.code()})",
                        date
                    )
                }
            } catch (e: Exception) {
                _uiState.value = MenuUiState.Error(
                    e.message ?: "Произошла неизвестная ошибка при загрузке меню",
                    date
                )
            }
        }
    }
}