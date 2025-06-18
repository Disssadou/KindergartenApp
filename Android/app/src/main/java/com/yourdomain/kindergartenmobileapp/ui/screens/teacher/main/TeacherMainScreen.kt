package com.yourdomain.kindergartenmobileapp.ui.screens.teacher.main

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.RestaurantMenu
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavController
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.yourdomain.kindergartenmobileapp.navigation.AppScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.menu.MenuScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.teacher.groups.TeacherGroupsScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.profile.ProfileScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.posts.PostsScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.notifications.NotificationsEventsScreen


sealed class TeacherBottomNavItem(val route: String, val icon: ImageVector, val label: String) {
    data object Groups : TeacherBottomNavItem("teacher_groups_tab", Icons.Filled.Groups, "Группы")
    data object Menu : TeacherBottomNavItem("teacher_menu_tab", Icons.Filled.RestaurantMenu, "Меню")
    data object Posts : TeacherBottomNavItem("teacher_posts_tab", Icons.Filled.Article, "Новости")
    data object Notifications : TeacherBottomNavItem("teacher_notifications_tab", Icons.Filled.Chat, "Сообщения")
    data object Profile : TeacherBottomNavItem("teacher_profile_tab", Icons.Filled.Person, "Профиль")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TeacherMainScreen(
    mainNavController: NavController,
    onLogout: () -> Unit
) {
    val bottomNavController = rememberNavController()
    val items = listOf(
        TeacherBottomNavItem.Groups,
        TeacherBottomNavItem.Menu,
        TeacherBottomNavItem.Posts,
        TeacherBottomNavItem.Notifications,
        TeacherBottomNavItem.Profile
    )

    val navBackStackEntry by bottomNavController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val currentScreen = items.find { it.route == currentRoute }

    Scaffold(

        bottomBar = {
            NavigationBar {
                val navBackStackEntry by bottomNavController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination

                items.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = screen.label) },
                        label = { Text(screen.label) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            bottomNavController.navigate(screen.route) {
                                popUpTo(bottomNavController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        TeacherNavHost(
            navController = bottomNavController,
            mainNavController = mainNavController,
            paddingValues = innerPadding,
            onLogout = onLogout
        )
    }
}

@Composable
fun TeacherNavHost(
    navController: NavHostController,
    mainNavController: NavController,
    paddingValues: PaddingValues,
    onLogout: () -> Unit
) {
    NavHost(
        navController = navController,
        startDestination = TeacherBottomNavItem.Groups.route,
        modifier = Modifier.padding(paddingValues)
    ) {
        composable(TeacherBottomNavItem.Groups.route) {
            TeacherGroupsScreen(


                onGroupSelected = { groupId, groupName ->
                    mainNavController.navigate(AppScreen.AttendanceMarking.createRoute(groupId, groupName))
                }
            )
        }
        composable(TeacherBottomNavItem.Menu.route) {
            MenuScreen()
        }
        composable(TeacherBottomNavItem.Posts.route) {
            PostsScreen(
                navController = mainNavController,
                onPostClicked = { postId ->
                    android.util.Log.d("TeacherNavHost", "Navigating to PostDetail with ID: $postId")


                    mainNavController.navigate(AppScreen.PostDetail.createRoute(postId))

                }
            )
        }
        composable(TeacherBottomNavItem.Notifications.route) {
            NotificationsEventsScreen(
                onNotificationClicked = { notificationId ->

                    android.util.Log.d("NotificationsEvents", "Clicked on ID: $notificationId")
                }
            )
        }
        composable(TeacherBottomNavItem.Profile.route) {
            ProfileScreen(
                onLogoutAction = onLogout
            )
        }
    }
}