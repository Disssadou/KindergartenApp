package com.yourdomain.kindergartenmobileapp.ui.screens.teacher.groups

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.yourdomain.kindergartenmobileapp.data.network.dto.GroupDto




@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TeacherGroupsScreen(

    onGroupSelected: (groupId: Int, groupName: String) -> Unit,
    viewModel: TeacherGroupsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Мои группы") },
                actions = {
                    IconButton(onClick = { viewModel.loadTeacherGroups() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить список групп")
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
                is TeacherGroupsUiState.Loading -> {
                    CircularProgressIndicator()
                }
                is TeacherGroupsUiState.Success -> {
                    if (state.groups.isEmpty()) {
                        Text("У вас пока нет назначенных групп.")
                    } else {
                        GroupsList(groups = state.groups, onGroupClick = onGroupSelected)
                    }
                }
                is TeacherGroupsUiState.Error -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Ошибка загрузки групп: ${state.message}", color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadTeacherGroups() }) {
                            Text("Попробовать снова")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GroupsList(
    groups: List<GroupDto>,
    onGroupClick: (groupId: Int, groupName: String) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(groups, key = { it.id }) { group ->
            GroupItem(group = group, onClick = {
                onGroupClick(group.id, group.name)
            })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GroupItem(
    group: GroupDto,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth()
        ) {
            Text(text = group.name, style = MaterialTheme.typography.titleMedium)
            if (group.description != null) {
                Text(
                    text = group.description,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2 // Ограничиваем описание
                )
            }

        }
    }
}