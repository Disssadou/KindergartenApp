package com.yourdomain.kindergartenmobileapp.ui.screens.teacher.groups

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.GroupDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject


sealed interface TeacherGroupsUiState {
    data object Loading : TeacherGroupsUiState
    data class Success(val groups: List<GroupDto>) : TeacherGroupsUiState
    data class Error(val message: String) : TeacherGroupsUiState
}

@HiltViewModel
class TeacherGroupsViewModel @Inject constructor(
    private val authApiService: AuthApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow<TeacherGroupsUiState>(TeacherGroupsUiState.Loading)
    val uiState: StateFlow<TeacherGroupsUiState> = _uiState.asStateFlow()

    init {
        loadTeacherGroups()
    }

    fun loadTeacherGroups() {
        _uiState.update { TeacherGroupsUiState.Loading }
        viewModelScope.launch {
            try {

                val userResponse = authApiService.getCurrentUser()
                if (userResponse.isSuccessful && userResponse.body() != null) {
                    val currentUser = userResponse.body()!!
                    if (currentUser.role.equals("teacher", ignoreCase = true) || currentUser.role.equals("admin", ignoreCase = true)) { // Админ тоже может видеть группы
                        val teacherId = currentUser.id


                        val groupsResponse = authApiService.getGroupsForTeacher(teacherId = teacherId)
                        if (groupsResponse.isSuccessful && groupsResponse.body() != null) {
                            _uiState.update { TeacherGroupsUiState.Success(groupsResponse.body()!!) }
                        } else {
                            val errorMsg = groupsResponse.errorBody()?.string() ?: "Не удалось загрузить группы (${groupsResponse.code()})"
                            _uiState.update { TeacherGroupsUiState.Error(errorMsg) }
                        }
                    } else {
                        _uiState.update { TeacherGroupsUiState.Error("Текущий пользователь не является воспитателем или администратором.") }
                    }
                } else {
                    val errorMsg = userResponse.errorBody()?.string() ?: "Не удалось получить данные пользователя (${userResponse.code()})"
                    _uiState.update { TeacherGroupsUiState.Error(errorMsg) }
                }
            } catch (e: Exception) {
                _uiState.update { TeacherGroupsUiState.Error(e.message ?: "Произошла неизвестная ошибка при загрузке групп") }
            }
        }
    }
}