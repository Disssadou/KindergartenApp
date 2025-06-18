package com.yourdomain.kindergartenmobileapp.ui.screens.common.posts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourdomain.kindergartenmobileapp.data.network.api.AuthApiService
import com.yourdomain.kindergartenmobileapp.data.network.dto.PostDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PostsScreenState(
    val posts: List<PostDto> = emptyList(),
    val isLoading: Boolean = false,
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    val canLoadMore: Boolean = true,
    val endReached: Boolean = false
)

@HiltViewModel
class PostsViewModel @Inject constructor(
    private val apiService: AuthApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(PostsScreenState(isLoading = true))
    val uiState: StateFlow<PostsScreenState> = _uiState.asStateFlow()

    private var currentPage = 0
    private val pageSize = 10

    init {
        loadPosts(initialLoad = true)
    }

    fun loadPosts(initialLoad: Boolean = false) {
        if (initialLoad) {
            currentPage = 0
            _uiState.update { it.copy(isLoading = true, posts = emptyList(), canLoadMore = true, endReached = false, error = null) }
        } else {
            if (_uiState.value.isLoadingMore || !_uiState.value.canLoadMore) return
            _uiState.update { it.copy(isLoadingMore = true, error = null) }
        }

        viewModelScope.launch {
            try {
                val response = apiService.getPosts(skip = currentPage * pageSize, limit = pageSize)
                if (response.isSuccessful && response.body() != null) {
                    val newPosts = response.body()!!
                    _uiState.update { currentState ->
                        currentState.copy(
                            posts = if (initialLoad) newPosts else currentState.posts + newPosts,
                            isLoading = false,
                            isLoadingMore = false,
                            canLoadMore = newPosts.size >= pageSize,
                            endReached = newPosts.isEmpty() && !initialLoad
                        )
                    }
                    if (newPosts.isNotEmpty()) {
                        currentPage++
                    }
                } else {
                    val errorMsg = response.errorBody()?.string() ?: "Ошибка загрузки постов (${response.code()})"
                    _uiState.update { it.copy(isLoading = false, isLoadingMore = false, error = errorMsg) }
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(isLoading = false, isLoadingMore = false, error = e.message ?: "Неизвестная ошибка") }
            }
        }
    }

    fun refreshPosts() {
        loadPosts(initialLoad = true)
    }
}