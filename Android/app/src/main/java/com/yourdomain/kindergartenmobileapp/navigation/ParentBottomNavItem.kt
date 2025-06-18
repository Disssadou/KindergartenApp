package com.yourdomain.kindergartenmobileapp.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChildCare
import androidx.compose.material.icons.filled.RestaurantMenu
import androidx.compose.material.icons.filled.Article

import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Chat
import androidx.compose.ui.graphics.vector.ImageVector

sealed class ParentBottomNavItem(val route: String, val label: String, val icon: ImageVector) {
    data object Children : ParentBottomNavItem("parent_children_list_tab", "Мои дети", Icons.Filled.ChildCare)
    data object Menu : ParentBottomNavItem("parent_menu_tab", "Меню", Icons.Filled.RestaurantMenu)
    data object Posts : ParentBottomNavItem("parent_posts_tab", "Новости", Icons.Filled.Article)
    data object Notifications : ParentBottomNavItem("parent_notifications_tab", "Сообщения", Icons.Filled.Chat)
    data object Profile : ParentBottomNavItem("parent_profile_tab", "Профиль", Icons.Filled.AccountCircle)
}


val parentBottomNavItemsList = listOf(
    ParentBottomNavItem.Children,
    ParentBottomNavItem.Menu,

    ParentBottomNavItem.Posts,
    ParentBottomNavItem.Notifications,
    ParentBottomNavItem.Profile
)