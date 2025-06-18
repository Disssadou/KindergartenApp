package com.yourdomain.kindergartenmobileapp.navigation

sealed class AppScreen(val route: String) {
    data object Splash : AppScreen("splash_screen")
    data object Login : AppScreen("login_screen")

    data object TeacherMain : AppScreen("teacher_main_screen")
    data object ParentDashboard : AppScreen("parent_dashboard_screen")
    data object AttendanceMarking : AppScreen("attendance_marking_screen/{groupId}/{groupName}") {
        fun createRoute(groupId: Int, groupName: String) = "attendance_marking_screen/$groupId/${java.net.URLEncoder.encode(groupName, "UTF-8")}"
    }
    data object ChildDetails : AppScreen("child_details_screen/{childId}") {
        fun createRoute(childId: Int) = "child_details_screen/$childId"
    }

    data object PostDetail : AppScreen("post_detail_screen/{postId}") {
        fun createRoute(postId: Int) = "post_detail_screen/$postId"
    }
}