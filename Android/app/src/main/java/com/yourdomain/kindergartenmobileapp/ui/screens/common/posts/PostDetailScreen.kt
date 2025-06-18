package com.yourdomain.kindergartenmobileapp.ui.screens.common.posts

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.PostDto
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface PostDetailUiState {
    data object Loading : PostDetailUiState
    data class Success(val post: PostDto) : PostDetailUiState
    data class Error(val message: String) : PostDetailUiState
}

@HiltViewModel
class PostDetailViewModel @Inject constructor(
    private val apiService: AuthApiService,
    savedStateHandle: SavedStateHandle
) : ViewModel() {
    private val postId: Int = checkNotNull(savedStateHandle["postId"])

    private val _uiState = MutableStateFlow<PostDetailUiState>(PostDetailUiState.Loading)
    val uiState: StateFlow<PostDetailUiState> = _uiState.asStateFlow()

    init {
        loadPostDetails()
    }

    fun loadPostDetails() {
        _uiState.value = PostDetailUiState.Loading
        viewModelScope.launch {
            try {
                val response = apiService.getPost(postId)
                if (response.isSuccessful && response.body() != null) {
                    _uiState.value = PostDetailUiState.Success(response.body()!!)
                } else {
                    _uiState.value = PostDetailUiState.Error(
                        response.errorBody()?.string() ?: "Не удалось загрузить пост (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = PostDetailUiState.Error(e.message ?: "Ошибка загрузки деталей поста")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PostDetailScreen(
    navController: NavController,
    viewModel: PostDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Детали новости") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Назад")
                    }
                }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            when (val state = uiState) {
                is PostDetailUiState.Loading -> CircularProgressIndicator()
                is PostDetailUiState.Success -> {
                    PostDetailContent(post = state.post)
                }
                is PostDetailUiState.Error -> {
                    Text("Ошибка: ${state.message}", color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

@Composable
fun PostDetailContent(post: PostDto) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState())
    ) {
        post.title?.let {
            Text(it, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(bottom = 8.dp))
        }


        if (post.mediaFiles.isNotEmpty()) {
            val firstMedia = post.mediaFiles[0]
            if (firstMedia.fileType.equals("photo", ignoreCase = true) || firstMedia.fileType.equals("image", ignoreCase = true)) {

                val imageUrl = "http://10.0.2.2:8000/uploads/post_media/${firstMedia.filePath.trimStart('/')}"

                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(imageUrl).crossfade(true).build(),
                    contentDescription = post.title ?: "Изображение к посту",
                    modifier = Modifier.fillMaxWidth().wrapContentHeight().clip(MaterialTheme.shapes.medium),
                    contentScale = ContentScale.Fit
                )
                Spacer(modifier = Modifier.height(16.dp))
            }
        }

        Text(post.textContent, style = MaterialTheme.typography.bodyLarge)
        Spacer(modifier = Modifier.height(16.dp))

    }
}