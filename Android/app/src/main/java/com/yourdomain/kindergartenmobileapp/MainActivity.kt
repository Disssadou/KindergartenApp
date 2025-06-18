package com.yourdomain.kindergartenmobileapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import com.yourdomain.kindergartenmobileapp.navigation.AppScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.login.LoginScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.teacher.attendance.AttendanceMarkingScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.teacher.main.TeacherMainScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.posts.PostDetailScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.parent.childdetails.ChildDetailsScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.splash.SplashScreen
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject
import com.yourdomain.kindergartenmobileapp.ui.theme.KindergartenMobileAppTheme

import com.yourdomain.kindergartenmobileapp.ui.screens.parent.main.ParentMainScreen


@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            KindergartenMobileAppTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AppNavigation()
                }
            }
        }
    }
}


@HiltViewModel
class LogoutViewModel @Inject constructor(
    private val tokenRepository: TokenRepository
) : ViewModel() {
    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            tokenRepository.clearToken()
            onLoggedOut()
        }
    }
}

@Composable
fun AppNavigation() {
    val navController = rememberNavController()
    val logoutViewModel: LogoutViewModel = hiltViewModel()

    NavHost(
        navController = navController,
        startDestination = AppScreen.Splash.route
    ) {
        composable(AppScreen.Splash.route) {
            SplashScreen(navController = navController)
        }

        composable(AppScreen.Login.route) {
            LoginScreen(
                onLoginSuccess = { userRole ->
                    val destination = when (userRole.lowercase()) {
                            "teacher", "admin" -> AppScreen.TeacherMain.route
                            "parent" -> AppScreen.ParentDashboard.route
                        else -> null
                    }
                    destination?.let {
                        navController.navigate(it) {
                            popUpTo(AppScreen.Login.route) { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                }
            )
        }

        composable(AppScreen.TeacherMain.route) {
            TeacherMainScreen(
                mainNavController = navController,
                onLogout = {
                    navController.navigate(AppScreen.Login.route) {
                        popUpTo(AppScreen.TeacherMain.route) { inclusive = true }
                        launchSingleTop = true

                    }
                }
            )
        }

        composable(AppScreen.ParentDashboard.route) {
            ParentMainScreen(
                mainNavController = navController,
                onLogout = {
                    logoutViewModel.logout {
                        navController.navigate(AppScreen.Login.route) {
                            popUpTo(navController.graph.startDestinationId) { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                }
            )
        }



        composable(
            route = AppScreen.AttendanceMarking.route,
            arguments = listOf(
                navArgument("groupId") { type = NavType.IntType },
                navArgument("groupName") { type = NavType.StringType }
            )
        ) {
            AttendanceMarkingScreen()
        }

        composable(
            route = AppScreen.PostDetail.route,
            arguments = listOf(navArgument("postId") { type = NavType.IntType })
        ) {

            PostDetailScreen(navController = navController)
        }

        composable(
            route = AppScreen.ChildDetails.route,
            arguments = listOf(navArgument("childId") { type = NavType.IntType })
        ) { backStackEntry ->
            val receivedChildId = backStackEntry.arguments?.getInt("childId")
            Timber.d("AppNavigation/ChildDetails: Navigated! ChildId: $receivedChildId")
            if (receivedChildId != null) {
                ChildDetailsScreen(navController = navController)
            } else {
                Timber.e("AppNavigation/ChildDetails: ERROR - childId is null in arguments!")

                Text("Ошибка: ID ребенка не передан.")
            }
        }
    }
}

