package com.yourdomain.kindergartenmobileapp.ui.screens.common.notifications

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
// import androidx.navigation.NavController
import com.yourdomain.kindergartenmobileapp.data.network.dto.NotificationDto
import com.yourdomain.kindergartenmobileapp.ui.components.NotificationListItem
import com.yourdomain.kindergartenmobileapp.ui.screens.common.posts.ErrorStatePosts
import com.yourdomain.kindergartenmobileapp.ui.screens.common.posts.EmptyStatePosts

data class TabItem(
    val title: String,
    val icon: ImageVector,
    val content: @Composable () -> Unit
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsEventsScreen(

    viewModel: NotificationsEventsViewModel = hiltViewModel(),
    onNotificationClicked: (notificationId: Int) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val tabItems = listOf(
        TabItem(
            title = "Уведомления",
            icon = Icons.Filled.Campaign,
            content = {
                NotificationListContent(
                    listState = uiState.notificationsState,
                    onLoadMore = { viewModel.loadNotifications() },
                    onRefresh = { viewModel.refreshNotifications() },
                    onItemClicked = onNotificationClicked,
                    isEventList = false
                )
            }
        ),
        TabItem(
            title = "События",
            icon = Icons.Filled.Event,
            content = {
                NotificationListContent(
                    listState = uiState.eventsState,
                    onLoadMore = { viewModel.loadEvents() },
                    onRefresh = { viewModel.refreshEvents() },
                    onItemClicked = onNotificationClicked,
                    isEventList = true
                )
            }
        )
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Сообщения и События") },
                actions = {
                    IconButton(onClick = {
                        if (uiState.selectedTabIndex == 0) viewModel.refreshNotifications()
                        else viewModel.refreshEvents()
                    }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(modifier = Modifier.padding(paddingValues)) {
            TabRow(selectedTabIndex = uiState.selectedTabIndex) {
                tabItems.forEachIndexed { index, item ->
                    Tab(
                        selected = uiState.selectedTabIndex == index,
                        onClick = { viewModel.onTabSelected(index) },
                        text = { Text(item.title) },
                        icon = { Icon(item.icon, contentDescription = item.title) }
                    )
                }
            }

            tabItems[uiState.selectedTabIndex].content()
        }
    }
}

@Composable
fun NotificationListContent(
    listState: NotificationsListState,
    onLoadMore: () -> Unit,
    onRefresh: () -> Unit,
    onItemClicked: (notificationId: Int) -> Unit,
    isEventList: Boolean
) {
    val lazyListState = rememberLazyListState()

    Box(modifier = Modifier.fillMaxSize()) {
        if (listState.isLoadingInitial && listState.items.isEmpty()) {
            CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
        } else if (listState.error != null && listState.items.isEmpty()) {
            ErrorStatePosts(message = listState.error, onRetry = onRefresh)
        } else if (listState.items.isEmpty() && !listState.isLoadingInitial && !listState.canLoadMore) {
            EmptyStatePosts(message = if(isEventList) "Событий пока нет." else "Уведомлений пока нет.", onRefresh = onRefresh)
        } else {
            LazyColumn(
                state = lazyListState,
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(listState.items, key = { it.id }) { notification ->
                    NotificationListItem(
                        notification = notification,
                        onNotificationClick = { onItemClicked(notification.id) }
                    )
                }
                item {
                    if (listState.isLoadingMore) {
                        Row(modifier = Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.Center) {
                            CircularProgressIndicator(modifier = Modifier.size(32.dp))
                        }
                    } else if (listState.canLoadMore && listState.error == null) {
                        OutlinedButton(onClick = onLoadMore, modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                            Text(if(isEventList) "Загрузить еще события" else "Загрузить еще уведомления")
                        }
                    } else if (listState.error != null) {
                        Text("Ошибка: ${listState.error}", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(8.dp))
                    } else if (!listState.canLoadMore && listState.items.isNotEmpty()){
                        Text(
                            if(isEventList) "Вы просмотрели все события" else "Вы просмотрели все уведомления",
                            modifier = Modifier.padding(16.dp).fillMaxWidth(), textAlign = TextAlign.Center
                        )
                    }
                }
            }


            val endOfListReached by remember {
                derivedStateOf {
                    val layoutInfo = lazyListState.layoutInfo
                    val visibleItemsInfo = layoutInfo.visibleItemsInfo
                    if (layoutInfo.totalItemsCount == 0) false
                    else visibleItemsInfo.lastOrNull()?.index == layoutInfo.totalItemsCount - 1
                }
            }
            LaunchedEffect(endOfListReached, listState.canLoadMore, listState.isLoadingMore, listState.isLoadingInitial) {
                if (endOfListReached && listState.canLoadMore && !listState.isLoadingMore && !listState.isLoadingInitial) {
                    onLoadMore()
                }
            }
        }
    }
}