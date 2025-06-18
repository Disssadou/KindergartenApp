package com.yourdomain.kindergartenmobileapp.ui.screens.teacher.attendance

import android.app.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import android.widget.DatePicker
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Done
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.ui.graphics.Color
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.yourdomain.kindergartenmobileapp.data.network.dto.AbsenceTypeDto
import timber.log.Timber
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttendanceMarkingScreen(

    viewModel: AttendanceMarkingViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val selectedDate by viewModel.selectedDate.collectAsState()
    val context = LocalContext.current


    val year = selectedDate.year
    val month = selectedDate.monthValue -1
    val day = selectedDate.dayOfMonth
    val datePickerDialog = DatePickerDialog(
        context,
        { _: DatePicker, selectedYear: Int, selectedMonth: Int, selectedDayOfMonth: Int ->
            viewModel.onDateSelected(LocalDate.of(selectedYear, selectedMonth + 1, selectedDayOfMonth))
        }, year, month, day
    )



    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    val titleText = when (val state = uiState) {
                        is AttendanceMarkingUiState.Success -> "Отметка: ${state.groupName}"
                        is AttendanceMarkingUiState.Error -> "Ошибка: ${state.groupName}"
                        else -> "Отметка посещаемости"
                    }
                    Text(titleText)
                },
                actions = {
                    IconButton(onClick = { datePickerDialog.show() }) {
                        Icon(Icons.Filled.DateRange, contentDescription = "Выбрать дату")
                    }
                    IconButton(onClick = { viewModel.loadAttendanceData(selectedDate) }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить")
                    }
                }
            )
        },
        floatingActionButton = {
            val currentState = uiState
            if (currentState is AttendanceMarkingUiState.Success && currentState.items.isNotEmpty()) {
                LargeFloatingActionButton(onClick = { viewModel.saveAttendance() }) {
                    Icon(Icons.Filled.Done, contentDescription = "Сохранить отметки")
                }
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            when (val state = uiState) {
                is AttendanceMarkingUiState.Loading -> {
                    CircularProgressIndicator()
                }
                is AttendanceMarkingUiState.Success -> {
                    Column {
                        Text(
                            text = "Дата: ${state.date.format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))}",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                        )
                        if (state.items.isEmpty()) {
                            Box(modifier=Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text("В этой группе нет детей.")
                            }
                        } else {
                            AttendanceList(
                                items = state.items,
                                onAttendanceChange = { childId, isPresent, type, reason ->
                                    viewModel.updateChildAttendance(childId, isPresent, type, reason)
                                }
                            )
                        }
                    }
                }
                is AttendanceMarkingUiState.Error -> {
                    Column(
                        modifier = Modifier.padding(16.dp).fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text("Ошибка: ${state.message}", color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadAttendanceData(state.date) }) {
                            Text("Попробовать снова")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun AttendanceList(
    items: List<ChildAttendanceDisplayItem>,
    onAttendanceChange: (childId: Int, isPresent: Boolean, type: AbsenceTypeDto?, reason: String?) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(items, key = { it.child.id }) { displayItem ->
            ChildAttendanceRow(
                item = displayItem,
                onAttendanceChange = onAttendanceChange
            )
            HorizontalDivider()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChildAttendanceRow(
    item: ChildAttendanceDisplayItem,
    onAttendanceChange: (childId: Int, isPresent: Boolean, type: AbsenceTypeDto?, reason: String?) -> Unit
) {
    var localReason by remember(item.child.id, item.uiAbsenceReason) { mutableStateOf(item.uiAbsenceReason ?: "") }

    var absenceTypeMenuExpanded by remember { mutableStateOf(false) }
    var selectedAbsenceType by remember(item.child.id, item.uiAbsenceType) { mutableStateOf(item.uiAbsenceType) }
    val checkboxColors = if (item.hasPendingChanges) {
        CheckboxDefaults.colors(
            checkedColor = MaterialTheme.colorScheme.secondary,
            uncheckedColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            checkmarkColor = MaterialTheme.colorScheme.onSecondary
        )
    } else {
        CheckboxDefaults.colors()
    }

    Card(modifier = Modifier.fillMaxWidth().border( //
        width = if (item.hasPendingChanges) 2.dp else 0.dp,
        color = if (item.hasPendingChanges) MaterialTheme.colorScheme.secondary else Color.Transparent,
        shape = CardDefaults.shape
    )) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = item.uiIsPresent,
                onCheckedChange = { isChecked ->
                    onAttendanceChange(item.child.id, isChecked, selectedAbsenceType, localReason)
                },
                colors = checkboxColors
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(item.child.fullName, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        }


        if (!item.uiIsPresent) {
            Column(modifier = Modifier.padding(start = 16.dp, end = 8.dp, bottom = 8.dp)) {
                ExposedDropdownMenuBox(
                    expanded = absenceTypeMenuExpanded,
                    onExpandedChange = { absenceTypeMenuExpanded = !absenceTypeMenuExpanded },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    OutlinedTextField(
                        value = selectedAbsenceType?.let { getAbsenceTypeDisplayString(it) } ?: "Выберите тип",
                        onValueChange = {  },
                        label = { Text("Тип отсутствия") },
                        readOnly = true,
                        trailingIcon = {
                            ExposedDropdownMenuDefaults.TrailingIcon(expanded = absenceTypeMenuExpanded)
                        },
                        colors = ExposedDropdownMenuDefaults.outlinedTextFieldColors(),
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth()

                    )
                    ExposedDropdownMenu(
                        expanded = absenceTypeMenuExpanded,
                        onDismissRequest = { absenceTypeMenuExpanded = false }
                    ) {
                        AbsenceTypeDto.values().forEach { type ->
                            DropdownMenuItem(
                                text = { Text(getAbsenceTypeDisplayString(type)) },
                                onClick = {
                                    selectedAbsenceType = type
                                    onAttendanceChange(item.child.id, false, type, localReason)
                                    absenceTypeMenuExpanded = false
                                }
                            )
                        }

                        if (AbsenceTypeDto.values().isEmpty()) {
                            DropdownMenuItem(
                                text = { Text("Нет доступных типов") },
                                onClick = { absenceTypeMenuExpanded = false },
                                enabled = false
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = localReason,
                    onValueChange = {
                        localReason = it

                        onAttendanceChange(item.child.id, false, selectedAbsenceType, it)
                    },
                    label = { Text("Причина отсутствия (если нужно)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        }
    }
}


fun getAbsenceTypeDisplayString(type: AbsenceTypeDto): String {
    return when (type) {
        AbsenceTypeDto.SICK_LEAVE -> "Больничный"
        AbsenceTypeDto.VACATION -> "Отпуск"
        AbsenceTypeDto.OTHER -> "Другое"
    }
}