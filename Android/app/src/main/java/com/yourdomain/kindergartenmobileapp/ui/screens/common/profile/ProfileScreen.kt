
package com.yourdomain.kindergartenmobileapp.ui.screens.common.profile

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.UserResponse
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import java.util.Locale


sealed interface ProfileUiState {
    data object Loading : ProfileUiState
    data class Success(val user: UserResponse) : ProfileUiState
    data class Error(val message: String) : ProfileUiState
}


@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val authApiService: AuthApiService,
    private val tokenRepository: TokenRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<ProfileUiState>(ProfileUiState.Loading)
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    init {
        loadUserProfile()
    }

    fun loadUserProfile() {
        _uiState.value = ProfileUiState.Loading
        viewModelScope.launch {
            try {
                val response = authApiService.getCurrentUser()
                if (response.isSuccessful && response.body() != null) {
                    _uiState.value = ProfileUiState.Success(response.body()!!)
                } else {
                    _uiState.value = ProfileUiState.Error(
                        response.errorBody()?.string() ?: "Не удалось загрузить профиль (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = ProfileUiState.Error(e.message ?: "Ошибка загрузки профиля")
            }
        }
    }

    fun logout(onLoggedOutCallback: () -> Unit) {
        viewModelScope.launch {
            tokenRepository.clearLoginCredentials()
            onLoggedOutCallback()
        }
    }
}


object UserRoleDisplayProfile {
    private val roleMap = mapOf(
        "admin" to "Администратор",
        "teacher" to "Воспитатель",
        "parent" to "Родитель"
    )
    fun getDisplayName(roleValue: String): String {
        return roleMap[roleValue.lowercase()] ?: roleValue.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }
    }
}


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    viewModel: ProfileViewModel = hiltViewModel(),
    onLogoutAction: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Профиль пользователя") })
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            when (val state = uiState) {
                is ProfileUiState.Loading -> CircularProgressIndicator()
                is ProfileUiState.Success -> {
                    UserProfileContent(user = state.user, onLogout = {
                        viewModel.logout(onLogoutAction)
                    })
                }
                is ProfileUiState.Error -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Ошибка: ${state.message}", color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadUserProfile() }) {
                            Text("Попробовать снова")
                        }
                    }
                }
            }
        }
    }
}


@Composable
fun UserProfileContent(user: UserResponse, onLogout: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize().padding(16.dp)
    ) {
        Icon(
            imageVector = Icons.Filled.AccountCircle,
            contentDescription = "Профиль",
            modifier = Modifier.size(96.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(16.dp))

        ProfileInfoRow(icon = Icons.Filled.Person, label = "ФИО:", value = user.fullName)
        ProfileInfoRow(
            icon = Icons.Filled.Work,
            label = "Роль:",
            value = UserRoleDisplayProfile.getDisplayName(user.role)
        )
        ProfileInfoRow(icon = Icons.Filled.Email, label = "Email:", value = user.email)
        user.phone?.let { ProfileInfoRow(icon = Icons.Filled.Phone, label = "Телефон:", value = it) }

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Filled.ExitToApp, contentDescription = "Выйти")
            Spacer(Modifier.size(ButtonDefaults.IconSpacing))
            Text("Выйти из аккаунта")
        }
    }
}


@Composable
fun ProfileInfoRow(icon: ImageVector, label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(imageVector = icon, contentDescription = label, modifier = Modifier.size(24.dp), tint = MaterialTheme.colorScheme.secondary)
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(text = label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text = value, style = MaterialTheme.typography.bodyLarge)
        }
    }
    Divider(modifier = Modifier.padding(vertical = 8.dp))
}