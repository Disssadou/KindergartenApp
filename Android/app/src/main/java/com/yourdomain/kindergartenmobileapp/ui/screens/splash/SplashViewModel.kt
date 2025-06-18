package com.yourdomain.kindergartenmobileapp.ui.screens.splash

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import com.yourdomain.kindergartenmobileapp.navigation.AppScreen
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface SplashDestination {
    data object Loading : SplashDestination
    data class NavigateTo(val route: String, val userRole: String? = null) : SplashDestination
}

@HiltViewModel
class SplashViewModel @Inject constructor(
    private val tokenRepository: TokenRepository,
    private val authApiService: AuthApiService
) : ViewModel() {

    private val _navigateTo = MutableStateFlow<SplashDestination>(SplashDestination.Loading)
    val navigateTo: StateFlow<SplashDestination> = _navigateTo.asStateFlow()

    init {
        checkUserLoggedIn()
    }

    private fun checkUserLoggedIn() {
        viewModelScope.launch {
            delay(1000)

            val shouldRemember = tokenRepository.shouldRememberMe()
            val token = tokenRepository.getToken()

            if (shouldRemember && !token.isNullOrBlank()) {

                try {

                    val userResponse = authApiService.getCurrentUser()
                    if (userResponse.isSuccessful && userResponse.body() != null) {
                        val userRole = userResponse.body()!!.role.lowercase()
                        val destination = when (userRole) {
                                "teacher", "admin" -> AppScreen.TeacherMain.route
                                "parent" -> AppScreen.ParentDashboard.route
                            else -> AppScreen.Login.route
                        }
                        _navigateTo.value = SplashDestination.NavigateTo(destination, userRole)
                    } else {

                        tokenRepository.clearLoginCredentials()
                        _navigateTo.value = SplashDestination.NavigateTo(AppScreen.Login.route)
                    }
                } catch (e: Exception) {

                    tokenRepository.clearLoginCredentials()
                    _navigateTo.value = SplashDestination.NavigateTo(AppScreen.Login.route)
                }
            } else {

                if (!shouldRemember) {
                    tokenRepository.clearLoginCredentials()
                }
                _navigateTo.value = SplashDestination.NavigateTo(AppScreen.Login.route)
            }
        }
    }
}