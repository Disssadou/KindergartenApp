package com.yourdomain.kindergartenmobileapp.ui.screens.common.menu

import android.app.DatePickerDialog
import android.widget.DatePicker
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.yourdomain.kindergartenmobileapp.data.network.dto.MealMenuDto
import com.yourdomain.kindergartenmobileapp.data.network.dto.MealTypeDto
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MenuScreen(

    viewModel: MenuViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val selectedDate by viewModel.selectedDate.collectAsState()
    val context = LocalContext.current

    // Date Picker Dialog
    val year = selectedDate.year
    val month = selectedDate.monthValue - 1
    val day = selectedDate.dayOfMonth
    val datePickerDialog = remember {
        DatePickerDialog(
            context,
            { _: DatePicker, selectedYear: Int, selectedMonth: Int, selectedDayOfMonth: Int ->
                viewModel.onDateSelected(LocalDate.of(selectedYear, selectedMonth + 1, selectedDayOfMonth))
            }, year, month, day
        ).apply {

        }
    }

    LaunchedEffect(selectedDate) {
        datePickerDialog.updateDate(selectedDate.year, selectedDate.monthValue - 1, selectedDate.dayOfMonth)
    }


    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Меню питания") },
                actions = {
                    IconButton(onClick = { datePickerDialog.show() }) {
                        Icon(Icons.Filled.DateRange, contentDescription = "Выбрать дату")
                    }
                    IconButton(onClick = { viewModel.loadMenuForDate() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить меню")
                    }
                }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize(),
            contentAlignment = Alignment.TopCenter
        ) {
            when (val state = uiState) {
                is MenuUiState.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                is MenuUiState.Success -> {
                    DailyMenuLayout(menuByMealType = state.menuByMealType, date = state.date)
                }
                is MenuUiState.Empty -> {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text("Меню на ${state.date.format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))} не найдено.")
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { datePickerDialog.show() }) {
                            Text("Выбрать другую дату")
                        }
                    }
                }
                is MenuUiState.Error -> {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text("Ошибка: ${state.message}", color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadMenuForDate(state.date) }) {
                            Text("Попробовать снова")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun DailyMenuLayout(menuByMealType: Map<MealTypeDto, List<MealMenuDto>>, date: LocalDate) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Text(
                text = "Меню на: ${date.format(DateTimeFormatter.ofPattern("dd MMMM yyyy"))}",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }


        val orderedMealTypes = MealTypeDto.values().sortedBy { it.ordinal }

        orderedMealTypes.forEach { mealType ->
            menuByMealType[mealType]?.let { dishes ->
                if (dishes.isNotEmpty()) {
                    item { MealTypeSection(mealType = mealType, dishes = dishes) }
                }
            }
        }

        if (menuByMealType.isEmpty()){
            item {
                Text("Информация о меню на эту дату отсутствует.", style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

@Composable
fun MealTypeSection(mealType: MealTypeDto, dishes: List<MealMenuDto>) {
    Column {
        Text(
            text = mealType.displayName,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(4.dp))
        dishes.forEach { dish ->
            Text(
                text = "- ${dish.description}",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(start = 8.dp)
            )
        }
    }
}