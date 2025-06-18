package com.yourdomain.kindergartenmobileapp.ui.screens.common.posts

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.yourdomain.kindergartenmobileapp.data.network.dto.PostDto
import com.yourdomain.kindergartenmobileapp.ui.components.PostItemView


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PostsScreen(
    viewModel: PostsViewModel = hiltViewModel(),
    navController: NavController,
    onPostClicked: (postId: Int) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val lazyListState = rememberLazyListState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Новости и Объявления") },
                actions = {
                    IconButton(onClick = { viewModel.refreshPosts() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить ленту")
                    }
                }
            )
        }

    ) { innerScaffoldPadding ->
        Box(
            modifier = Modifier
                .padding(innerScaffoldPadding)
                .fillMaxSize(),
        ) {
            if (uiState.isLoading && uiState.posts.isEmpty()) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else if (uiState.error != null && uiState.posts.isEmpty()) {
                ErrorStatePosts(message = uiState.error!!, onRetry = { viewModel.refreshPosts() })
            } else if (uiState.posts.isEmpty() && !uiState.isLoading && !uiState.canLoadMore) {
                EmptyStatePosts(message = "Пока нет новостей.", onRefresh = {viewModel.refreshPosts()})
            }
            else {
                PostsListContent(
                    posts = uiState.posts,
                    isLoadingMore = uiState.isLoadingMore,
                    canLoadMore = uiState.canLoadMore,
                    errorLoadingMore = if (uiState.isLoadingMore || uiState.isLoading) null else uiState.error,
                    onLoadMore = { viewModel.loadPosts() },
                    onPostClicked = onPostClicked,
                    listState = lazyListState
                )
            }
        }
    }

    val endOfListReached by remember {
        derivedStateOf {
            val layoutInfo = lazyListState.layoutInfo
            val visibleItemsInfo = layoutInfo.visibleItemsInfo
            if (layoutInfo.totalItemsCount == 0) {
                false
            } else {
                visibleItemsInfo.lastOrNull()?.index == layoutInfo.totalItemsCount - 1
            }
        }
    }

    LaunchedEffect(endOfListReached) {
        if (endOfListReached && uiState.canLoadMore && !uiState.isLoadingMore && !uiState.isLoading) {
            viewModel.loadPosts()
        }
    }
}

@Composable
fun PostsListContent(
    posts: List<PostDto>,
    isLoadingMore: Boolean,
    canLoadMore: Boolean,
    errorLoadingMore: String?,
    onLoadMore: () -> Unit,
    onPostClicked: (postId: Int) -> Unit,
    listState: androidx.compose.foundation.lazy.LazyListState
) {
    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(posts, key = { it.id }) { post ->
            PostItemView(
                post = post,
                onPostClick = { onPostClicked(post.id) },
                modifier = Modifier.padding(horizontal = 8.dp)
            )
        }

        item {
            if (isLoadingMore) {
                Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.Center) {
                    CircularProgressIndicator(modifier = Modifier.size(32.dp))
                }
            } else if (canLoadMore && errorLoadingMore == null) {
                OutlinedButton(
                    onClick = onLoadMore,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)
                ) {
                    Text("Загрузить еще")
                }
            } else if (errorLoadingMore != null) {
                Text("Ошибка загрузки: $errorLoadingMore", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
            } else if (!canLoadMore && posts.isNotEmpty()){
                Text("Вы просмотрели все новости", modifier = Modifier.padding(16.dp).fillMaxWidth(), textAlign = TextAlign.Center)
            }
        }
    }
}


@Composable
fun ErrorStatePosts(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(Icons.Filled.CloudOff, contentDescription = "Ошибка", modifier = Modifier.size(48.dp), tint = MaterialTheme.colorScheme.error)
        Spacer(modifier = Modifier.height(16.dp))
        Text(text = message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center)
        Spacer(modifier = Modifier.height(16.dp))
        Button(onClick = onRetry) {
            Text("Попробовать снова")
        }
    }
}

@Composable
fun EmptyStatePosts(message: String, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(text = message, style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(16.dp))
        OutlinedButton(onClick = onRefresh) {
            Text("Обновить")
        }
    }
}