
package com.yourdomain.kindergartenmobileapp.ui.screens.parent.main

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavController
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.yourdomain.kindergartenmobileapp.navigation.AppScreen
import com.yourdomain.kindergartenmobileapp.navigation.ParentBottomNavItem
import com.yourdomain.kindergartenmobileapp.navigation.ParentBottomNavigation
import com.yourdomain.kindergartenmobileapp.ui.screens.common.menu.MenuScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.notifications.NotificationsEventsScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.posts.PostsScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.common.profile.ProfileScreen
import com.yourdomain.kindergartenmobileapp.ui.screens.parent.childrenlist.ParentChildrenListScreen
import timber.log.Timber

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentMainScreen(
    mainNavController: NavController,
    onLogout: () -> Unit
) {
    val bottomParentNavController = rememberNavController()

    Scaffold(
        bottomBar = {
            ParentBottomNavigation(navController = bottomParentNavController)
        }
    ) { innerPadding ->
        ParentNavHost(
            bottomNavController = bottomParentNavController,
            mainNavController = mainNavController,
            paddingValues = innerPadding,
            onLogout = onLogout
        )
    }
}

@Composable
fun ParentNavHost(
    bottomNavController: NavHostController,
    mainNavController: NavController,
    paddingValues: PaddingValues,
    onLogout: () -> Unit
) {
    NavHost(
        navController = bottomNavController,
        startDestination = ParentBottomNavItem.Children.route,
        modifier = Modifier.padding(paddingValues)
    ) {
        composable(ParentBottomNavItem.Children.route) {
            ParentChildrenListScreen(
                onChildSelected = { childId, childName ->
                    Timber.d("Parent: Child ID=$childId, Name=$childName. Navigating to details.")
                    mainNavController.navigate(AppScreen.ChildDetails.createRoute(childId))
                },
                onLogout = onLogout
            )
        }
        composable(ParentBottomNavItem.Menu.route) {
            MenuScreen()
        }
        composable(ParentBottomNavItem.Posts.route) {
            PostsScreen(
                navController = mainNavController,
                onPostClicked = { postId ->
                    mainNavController.navigate(AppScreen.PostDetail.createRoute(postId))
                }

            )
        }
        composable(ParentBottomNavItem.Notifications.route) {
            NotificationsEventsScreen(
                onNotificationClicked = { notificationId ->

                    Timber.d("Parent: Notification/Event clicked ID: $notificationId")
                }

            )
        }
        composable(ParentBottomNavItem.Profile.route) {
            ProfileScreen(
                onLogoutAction = onLogout
            )
        }
    }
}