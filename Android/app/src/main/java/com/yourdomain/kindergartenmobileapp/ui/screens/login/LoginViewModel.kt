package com.yourdomain.kindergartenmobileapp.ui.screens.login

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.UserResponse
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import javax.inject.Inject


sealed interface LoginUiState {
    data object Idle : LoginUiState
    data object Loading : LoginUiState
    data class Success(val user: UserResponse) : LoginUiState
    data class Error(val message: String) : LoginUiState
}

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authApiService: AuthApiService,
    private val tokenRepository: TokenRepository
) : ViewModel() {

    var usernameInput by mutableStateOf("")
        private set

    var passwordInput by mutableStateOf("")
        private set

    var rememberMeChecked by mutableStateOf(false)
        private set

    private val _loginUiState = MutableStateFlow<LoginUiState>(LoginUiState.Idle)
    val loginUiState: StateFlow<LoginUiState> = _loginUiState.asStateFlow()

    init {
        viewModelScope.launch {
            val shouldRemember = tokenRepository.shouldRememberMe()
            rememberMeChecked = shouldRemember
            if (shouldRemember) {
                tokenRepository.getLastUsername()?.let { lastUser ->
                    usernameInput = lastUser
                }
            }
        }
    }

    fun onUsernameChange(newUsername: String) {
        usernameInput = newUsername
    }

    fun onPasswordChange(newPassword: String) {
        passwordInput = newPassword
    }

    fun onRememberMeChange(isChecked: Boolean) { rememberMeChecked = isChecked }

    fun loginUser() {
        if (usernameInput.isBlank() || passwordInput.isBlank()) {
            _loginUiState.update { LoginUiState.Error("Имя пользователя и пароль не могут быть пустыми.") }
            return
        }

        _loginUiState.update { LoginUiState.Loading }
        viewModelScope.launch {
            try {
                val tokenResponse = authApiService.login(usernameInput, passwordInput)
                if (tokenResponse.isSuccessful && tokenResponse.body() != null) {
                    val token = tokenResponse.body()!!.accessToken
                    tokenRepository.saveToken(token)
                    tokenRepository.saveRememberMe(rememberMeChecked)
                    if (rememberMeChecked) {
                        tokenRepository.saveLastUsername(usernameInput)
                    } else {
                        tokenRepository.saveLastUsername("")
                    }


                    val userResponse = authApiService.getCurrentUser()
                    if (userResponse.isSuccessful && userResponse.body() != null) {
                        _loginUiState.update { LoginUiState.Success(userResponse.body()!!) }
                    } else {
                        tokenRepository.clearLoginCredentials()
                        val errorMsg = userResponse.errorBody()?.string() ?: "Не удалось получить данные пользователя (${userResponse.code()})"
                        _loginUiState.update { LoginUiState.Error(errorMsg) }
                    }
                } else {
                    val errorCode = tokenResponse.code()
                    val errorBodyString = tokenResponse.errorBody()?.string()
                    var displayErrorMessage = "Ошибка входа (${errorCode})"

                    if (errorCode == 401) {
                        displayErrorMessage = "Неверное имя пользователя или пароль."

                    } else if (errorCode == 422) {
                        val specificErrorMsg = parseFastApiError(errorBodyString)
                        displayErrorMessage = specificErrorMsg ?: "Ошибка валидации данных при входе."
                    } else if (errorBodyString != null) {

                        val specificErrorMsg = parseFastApiError(errorBodyString)
                        displayErrorMessage = specificErrorMsg ?: displayErrorMessage
                    }
                    _loginUiState.update { LoginUiState.Error(displayErrorMessage) }
                }
            } catch (e: Exception) {
                _loginUiState.update { LoginUiState.Error(e.message ?: "Произошла неизвестная ошибка") }
            }
        }
    }

    private fun parseFastApiError(errorBody: String?): String? {
        if (errorBody == null) return null
        return try {

            val gson = Gson()
            val type = object : TypeToken<Map<String, Any>>() {}.type
            val errorMap: Map<String, Any> = gson.fromJson(errorBody, type)

            when (val detail = errorMap["detail"]) {
                is String -> detail
                is List<*> -> {
                    (detail.firstOrNull() as? Map<*, *>)?.get("msg") as? String ?: errorBody
                }
                else -> errorBody
            }
        } catch (e: Exception) {

            errorBody.take(100) 
        }
    }

    fun resetLoginState() {
        _loginUiState.update { LoginUiState.Idle }
    }
}