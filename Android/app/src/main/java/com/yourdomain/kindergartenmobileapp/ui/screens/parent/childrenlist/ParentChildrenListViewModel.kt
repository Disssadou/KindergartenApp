package com.yourdomain.kindergartenmobileapp.ui.screens.parent.childrenlist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildParentAssociationDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject


sealed interface ParentChildrenListUiState {
    data object Loading : ParentChildrenListUiState
    data class Success(val childrenAssociations: List<ChildParentAssociationDto>) : ParentChildrenListUiState
    data class Error(val message: String) : ParentChildrenListUiState
}

@HiltViewModel
class ParentChildrenListViewModel @Inject constructor(
    private val authApiService: AuthApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow<ParentChildrenListUiState>(ParentChildrenListUiState.Loading)
    val uiState: StateFlow<ParentChildrenListUiState> = _uiState.asStateFlow()

    init {
        loadChildrenForCurrentUser()
    }

    fun loadChildrenForCurrentUser() {
        _uiState.update { ParentChildrenListUiState.Loading }
        viewModelScope.launch {
            try {

                val currentUserResponse = authApiService.getCurrentUser()
                if (!currentUserResponse.isSuccessful || currentUserResponse.body() == null) {
                    val errorMsg = currentUserResponse.errorBody()?.string() ?: "Не удалось получить данные текущего пользователя (${currentUserResponse.code()})"
                    Timber.e("Failed to get current user: $errorMsg")
                    _uiState.update { ParentChildrenListUiState.Error(errorMsg) }
                    return@launch
                }

                val currentUserId = currentUserResponse.body()!!.id
                Timber.d("Current user ID: $currentUserId")


                val childrenResponse = authApiService.getChildrenForUser(userId = currentUserId)

                if (childrenResponse.isSuccessful && childrenResponse.body() != null) {
                    _uiState.update { ParentChildrenListUiState.Success(childrenResponse.body()!!) }
                    Timber.i("Successfully loaded ${childrenResponse.body()!!.size} children for user $currentUserId")
                } else {
                    val errorMsg = childrenResponse.errorBody()?.string()
                        ?: "Не удалось загрузить список детей (${childrenResponse.code()})"
                    Timber.e("Failed to load children for user $currentUserId: $errorMsg")
                    _uiState.update { ParentChildrenListUiState.Error(errorMsg) }
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception while loading children for current user")
                _uiState.update { ParentChildrenListUiState.Error(e.message ?: "Произошла неизвестная ошибка при загрузке списка детей") }
            }
        }
    }
}