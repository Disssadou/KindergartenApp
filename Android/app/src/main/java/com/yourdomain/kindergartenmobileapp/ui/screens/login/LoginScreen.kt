package com.yourdomain.kindergartenmobileapp.ui.screens.login

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

import androidx.compose.material3.Checkbox
import androidx.compose.foundation.clickable



object UserRoleDisplay {
    private val roleMap = mapOf(
        "admin" to "Администратор",
        "teacher" to "Воспитатель",
        "parent" to "Родитель"
    )

    fun getDisplayName(roleValue: String): String {
        return roleMap[roleValue.lowercase()] ?: roleValue.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
    }
}

@Composable
fun LoginScreen(

    onLoginSuccess: (userRole: String) -> Unit,
    viewModel: LoginViewModel = hiltViewModel()
) {
    val uiState by viewModel.loginUiState.collectAsState()
    val context = LocalContext.current


    LaunchedEffect(key1 = uiState) {
        when (val state = uiState) {
            is LoginUiState.Success -> {
                Toast.makeText(context, "Вход успешен! Роль: ${UserRoleDisplay.getDisplayName(state.user.role)}", Toast.LENGTH_LONG).show()

                onLoginSuccess(state.user.role)
                viewModel.resetLoginState()
            }
            is LoginUiState.Error -> {
                Toast.makeText(context, "Ошибка: ${state.message}", Toast.LENGTH_LONG).show()
                viewModel.resetLoginState()
            }
            else -> {  }
        }
    }

    Surface(modifier = Modifier.fillMaxSize()) {
        Box(contentAlignment = Alignment.Center) {
            if (uiState is LoginUiState.Loading) {
                CircularProgressIndicator()
            } else {
                LoginContent(
                    username = viewModel.usernameInput,
                    password = viewModel.passwordInput,
                    rememberMe = viewModel.rememberMeChecked,
                    onUsernameChange = viewModel::onUsernameChange,
                    onPasswordChange = viewModel::onPasswordChange,
                    onRememberMeChange = viewModel::onRememberMeChange,
                    onLoginClick = viewModel::loginUser,
                    isLoading = uiState is LoginUiState.Loading
                )
            }
        }
    }
}

@Composable
fun LoginContent(
    username: String,
    password: String,
    rememberMe: Boolean,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onRememberMeChange: (Boolean) -> Unit,
    onLoginClick: () -> Unit,
    isLoading: Boolean
) {
    Column(
        modifier = Modifier
            .padding(32.dp)
            .fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("Вход в систему", style = MaterialTheme.typography.headlineSmall)

        OutlinedTextField(
            value = username,
            onValueChange = onUsernameChange,
            label = { Text("Имя пользователя") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Text,
                imeAction = ImeAction.Next
            ),
            modifier = Modifier.fillMaxWidth()
        )

        OutlinedTextField(
            value = password,
            onValueChange = onPasswordChange,
            label = { Text("Пароль") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),

            modifier = Modifier.fillMaxWidth()
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onRememberMeChange(!rememberMe) }
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = rememberMe,
                onCheckedChange = onRememberMeChange
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text("Запомнить меня")
        }

        Button(
            onClick = onLoginClick,
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text("Войти")
            }
        }
    }
}