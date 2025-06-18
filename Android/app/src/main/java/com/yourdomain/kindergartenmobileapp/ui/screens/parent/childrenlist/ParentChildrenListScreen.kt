package com.yourdomain.kindergartenmobileapp.ui.screens.parent.childrenlist

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
import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildParentAssociationDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildSimpleDto
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.runtime.remember

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentChildrenListScreen(

    onChildSelected: (childId: Int, childName: String) -> Unit,
    onLogout: () -> Unit,
    viewModel: ParentChildrenListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Мои дети") },
                actions = {
                    IconButton(onClick = { viewModel.loadChildrenForCurrentUser() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить список детей")
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
                is ParentChildrenListUiState.Loading -> {
                    CircularProgressIndicator()
                }
                is ParentChildrenListUiState.Success -> {
                    if (state.childrenAssociations.isEmpty()) {
                        Text("У вас пока нет привязанных детей в системе.")
                    } else {
                        ChildrenList(
                            associations = state.childrenAssociations,
                            onChildClick = { child ->
                                onChildSelected(child.id, child.fullName)
                            }
                        )
                    }
                }
                is ParentChildrenListUiState.Error -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Ошибка загрузки: ${state.message}", color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadChildrenForCurrentUser() }) {
                            Text("Попробовать снова")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChildrenList(
    associations: List<ChildParentAssociationDto>,
    onChildClick: (child: ChildSimpleDto) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(associations, key = { it.childId }) { association ->
            ChildItem(
                child = association.child,
                onClick = { onChildClick(association.child) }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChildItem(
    child: ChildSimpleDto,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = child.fullName, style = MaterialTheme.typography.titleMedium)

            Column(horizontalAlignment = Alignment.End) {
                if (child.lastChargeYear != null && child.lastChargeMonth != null && child.lastChargeAmount != null) {
                    val monthName = remember(child.lastChargeMonth) {

                        getMonthName(child.lastChargeMonth ?: 0)
                    }
                    Text(
                        text = "За $monthName ${child.lastChargeYear}:",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = "${"%.2f".format(child.lastChargeAmount)} руб.",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                } else {
                    Text(
                        text = "Нет начислений",
                        style = MaterialTheme.typography.bodySmall,
                        fontStyle = FontStyle.Italic
                    )
                }
            }
        }
    }
}
fun getMonthName(monthNumber: Int): String {
    // monthNumber здесь ожидается 1-12 (как приходит от API)
    return when (monthNumber) {
        1 -> "январь"
        2 -> "февраль"
        3 -> "март"
        4 -> "апрель"
        5 -> "май"
        6 -> "июнь"
        7 -> "июль"
        8 -> "август"
        9 -> "сентябрь"
        10 -> "октябрь"
        11 -> "ноябрь"
        12 -> "декабрь"
        else -> "Ошибка месяца"
    }

}