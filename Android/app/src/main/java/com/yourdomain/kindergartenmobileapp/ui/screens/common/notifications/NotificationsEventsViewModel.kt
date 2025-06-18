// NotificationsEventsViewModel.kt
package com.yourdomain.kindergartenmobileapp.ui.screens.common.notifications

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.NotificationDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.NotificationAudienceDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

data class NotificationsListState(
    val items: List<NotificationDto> = emptyList(),
    val isLoadingInitial: Boolean = false,
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    val canLoadMore: Boolean = true,
    val page: Int = 0
)

data class NotificationsEventsScreenState(
    val notificationsState: NotificationsListState = NotificationsListState(isLoadingInitial = true),
    val eventsState: NotificationsListState = NotificationsListState(isLoadingInitial = true),
    val selectedTabIndex: Int = 0,
    val currentUserRole: String? = null
)

@HiltViewModel
class NotificationsEventsViewModel @Inject constructor(
    private val apiService: AuthApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(NotificationsEventsScreenState())
    val uiState: StateFlow<NotificationsEventsScreenState> = _uiState.asStateFlow()

    private val pageSize = 15

    init {
        fetchCurrentUserRoleAndLoadData()
    }

    private fun fetchCurrentUserRoleAndLoadData() {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    notificationsState = it.notificationsState.copy(isLoadingInitial = true, items = emptyList(), page = 0, canLoadMore = true, error = null),
                    eventsState = it.eventsState.copy(isLoadingInitial = true, items = emptyList(), page = 0, canLoadMore = true, error = null),
                    currentUserRole = null
                )
            }
            try {
                val userResponse = apiService.getCurrentUser()
                if (userResponse.isSuccessful && userResponse.body() != null) {
                    val role = userResponse.body()!!.role.lowercase()
                    _uiState.update { it.copy(currentUserRole = role) }
                    Timber.d("Current user role fetched: $role")

                    loadNotifications(initialLoad = true, userRole = role)
                    loadEvents(initialLoad = true, userRole = role)
                } else {
                    val errorMsg = userResponse.errorBody()?.string() ?: "Не удалось получить роль пользователя"
                    Timber.e("Error fetching user role: $errorMsg")
                    _uiState.update {
                        it.copy(
                            notificationsState = it.notificationsState.copy(isLoadingInitial = false, error = errorMsg),
                            eventsState = it.eventsState.copy(isLoadingInitial = false, error = errorMsg),
                            currentUserRole = null
                        )
                    }
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception fetching user role")
                val errorMsg = e.message ?: "Ошибка сети при получении роли"
                _uiState.update {
                    it.copy(
                        notificationsState = it.notificationsState.copy(isLoadingInitial = false, error = errorMsg),
                        eventsState = it.eventsState.copy(isLoadingInitial = false, error = errorMsg),
                        currentUserRole = null
                    )
                }
            }
        }
    }

    fun onTabSelected(index: Int) {
        _uiState.update { it.copy(selectedTabIndex = index) }

        val currentSt = _uiState.value
        if (index == 0 && (currentSt.notificationsState.items.isEmpty() || currentSt.notificationsState.error != null) && !currentSt.notificationsState.isLoadingInitial && !currentSt.notificationsState.isLoadingMore) {
            loadNotifications(initialLoad = true, userRole = currentSt.currentUserRole)
        } else if (index == 1 && (currentSt.eventsState.items.isEmpty() || currentSt.eventsState.error != null) && !currentSt.eventsState.isLoadingInitial && !currentSt.eventsState.isLoadingMore) {
            loadEvents(initialLoad = true, userRole = currentSt.currentUserRole)
        }
    }

    fun loadNotifications(initialLoad: Boolean = false, userRole: String? = _uiState.value.currentUserRole) {
        val currentNotificationsState = _uiState.value.notificationsState
        if (userRole == null) {
            Timber.d("loadNotifications: userRole is null. Load will be triggered by fetchCurrentUserRoleAndLoadData or refresh.")
            if (initialLoad) _uiState.update { it.copy(notificationsState = it.notificationsState.copy(isLoadingInitial = false, error = "Роль пользователя еще не загружена")) }
            return
        }
        if (!initialLoad && (currentNotificationsState.isLoadingInitial || currentNotificationsState.isLoadingMore || !currentNotificationsState.canLoadMore)) {
            return
        }

        val pageToLoad = if (initialLoad) 0 else currentNotificationsState.page

        _uiState.update {
            it.copy(notificationsState = it.notificationsState.copy(
                isLoadingInitial = initialLoad,
                isLoadingMore = !initialLoad,
                error = null,
                page = if (initialLoad) 0 else it.notificationsState.page,
                items = if (initialLoad) emptyList() else it.notificationsState.items,
                canLoadMore = if (initialLoad) true else it.notificationsState.canLoadMore
            ))
        }

        viewModelScope.launch {
            try {
                val response = apiService.getNotifications(skip = pageToLoad * pageSize, limit = pageSize, isEvent = false)
                if (response.isSuccessful && response.body() != null) {
                    val allFetchedNotifications = response.body()!!
                    val filteredNotifications = filterNotificationsByRole(allFetchedNotifications, userRole)
                    Timber.d("Fetched ${allFetchedNotifications.size} notifications, filtered to ${filteredNotifications.size} for role $userRole")
                    _uiState.update { currentState ->
                        val oldItems = if (initialLoad) emptyList() else currentState.notificationsState.items
                        currentState.copy(
                            notificationsState = currentState.notificationsState.copy(
                                items = oldItems + filteredNotifications,
                                isLoadingInitial = false, isLoadingMore = false,
                                canLoadMore = allFetchedNotifications.size >= pageSize,
                                page = pageToLoad + 1
                            )
                        )
                    }
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Ошибка загрузки уведомлений (${response.code()})"
                    _uiState.update { it.copy(notificationsState = it.notificationsState.copy(isLoadingInitial = false, isLoadingMore = false,  error = errorMsg)) }
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception loading notifications")
                _uiState.update { it.copy(notificationsState = it.notificationsState.copy(isLoadingInitial = false, isLoadingMore = false, error = e.message ?: "Неизвестная ошибка")) }
            }
        }
    }

    fun loadEvents(initialLoad: Boolean = false, userRole: String? = _uiState.value.currentUserRole) {
        val currentEventsState = _uiState.value.eventsState
        if (userRole == null) {
            Timber.d("loadEvents: userRole is null. Load will be triggered by fetchCurrentUserRoleAndLoadData or refresh.")
            if (initialLoad) _uiState.update { it.copy(eventsState = it.eventsState.copy(isLoadingInitial = false, error = "Роль пользователя еще не загружена")) }
            return
        }
        if (!initialLoad && (currentEventsState.isLoadingInitial || currentEventsState.isLoadingMore || !currentEventsState.canLoadMore)) {
            return
        }

        val pageToLoad = if (initialLoad) 0 else currentEventsState.page

        _uiState.update {
            it.copy(eventsState = it.eventsState.copy(
                isLoadingInitial = initialLoad, isLoadingMore = !initialLoad, error = null,
                page = if(initialLoad) 0 else it.eventsState.page,
                items = if(initialLoad) emptyList() else it.eventsState.items,
                canLoadMore = if(initialLoad) true else it.eventsState.canLoadMore
            ))
        }
        viewModelScope.launch {
            try {
                val response = apiService.getNotifications(skip = pageToLoad * pageSize, limit = pageSize, isEvent = true)
                if (response.isSuccessful && response.body() != null) {
                    val allFetchedEvents = response.body()!!
                    val filteredEvents = filterNotificationsByRole(allFetchedEvents, userRole)
                    Timber.d("Fetched ${allFetchedEvents.size} events, filtered to ${filteredEvents.size} for role $userRole")
                    _uiState.update { currentState ->
                        val oldItems = if (initialLoad) emptyList() else currentState.eventsState.items
                        currentState.copy(
                            eventsState = currentState.eventsState.copy(
                                items = oldItems + filteredEvents,
                                isLoadingInitial = false, isLoadingMore = false,
                                canLoadMore = allFetchedEvents.size >= pageSize,
                                page = pageToLoad + 1
                            )
                        )
                    }
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Ошибка загрузки событий (${response.code()})"
                    _uiState.update { it.copy(eventsState = it.eventsState.copy(isLoadingInitial = false, isLoadingMore = false, error = errorMsg)) }
                }
            } catch (e: Exception) {
                Timber.e(e, "Exception loading events")
                _uiState.update { it.copy(eventsState = it.eventsState.copy(isLoadingInitial = false, isLoadingMore = false, error = e.message ?: "Неизвестная ошибка")) }
            }
        }
    }

    private fun filterNotificationsByRole(
        notifications: List<NotificationDto>,
        userRole: String?
    ): List<NotificationDto> {
        if (userRole == null) return emptyList()


        return notifications.filter { notification ->
            val audienceValue = notification.audienceRaw?.lowercase()
            when (userRole) {
                "parent" -> audienceValue == NotificationAudienceDto.ALL.value || audienceValue == NotificationAudienceDto.PARENTS.value
                "teacher" -> audienceValue == NotificationAudienceDto.ALL.value || audienceValue == NotificationAudienceDto.TEACHERS.value
                "admin" -> true
                else -> audienceValue == NotificationAudienceDto.ALL.value
            }
        }
    }

    fun refreshNotifications() {
        if (_uiState.value.currentUserRole == null) { fetchCurrentUserRoleAndLoadData() }
        else { loadNotifications(initialLoad = true, userRole = _uiState.value.currentUserRole) }
    }

    fun refreshEvents() {
        if (_uiState.value.currentUserRole == null) { fetchCurrentUserRoleAndLoadData() }
        else { loadEvents(initialLoad = true, userRole = _uiState.value.currentUserRole) }
    }
}