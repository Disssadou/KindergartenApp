package com.yourdomain.kindergartenmobileapp.ui.screens.parent.childdetails


import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack

import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController

import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildDetailResponseDto

import com.yourdomain.kindergartenmobileapp.data.network.dto.MonthlyChargeDto

import java.time.LocalDate
import java.time.OffsetDateTime

import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale


val ENGLISH_TO_RUSSIAN_MONTH_MAP_MOBILE = mapOf(
    "January" to "Январь", "February" to "Февраль", "March" to "Март", "April" to "Апрель",
    "May" to "Май", "June" to "Июнь", "July" to "Июль", "August" to "Август",
    "September" to "Сентябрь", "October" to "Октябрь", "November" to "Ноябрь", "December" to "Декабрь"
)

fun translateMonthsInText(text: String?, monthMap: Map<String, String>): String? {
    if (text == null) return null
    var currentResult: String = text

    for ((engMonth, rusMonth) in monthMap) {
        if (currentResult.contains(engMonth, ignoreCase = true)) {
            currentResult = currentResult.replace(engMonth, rusMonth, ignoreCase = true)
        }
    }
    return currentResult
}


fun getMonthName(monthNumber: Int, locale: Locale = Locale("ru")): String {
    if (monthNumber < 1 || monthNumber > 12) return "Ошибка месяца"
    return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
        java.time.Month.of(monthNumber).getDisplayName(java.time.format.TextStyle.FULL_STANDALONE, locale)
    } else {

        val months = arrayOf("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")
        months[monthNumber - 1]
    }
}


fun formatDateTime(isoDateTimeString: String?, pattern: String = "dd.MM.yyyy HH:mm"): String {
    if (isoDateTimeString.isNullOrBlank()) return "Нет данных"
    return try {
        OffsetDateTime.parse(isoDateTimeString)
            .format(DateTimeFormatter.ofPattern(pattern, Locale("ru")))
    } catch (e: Exception) {
        isoDateTimeString
    }
}


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChildDetailsScreen(
    navController: NavController,
    viewModel: ChildDetailsViewModel = hiltViewModel()
) {
    val childInfoState by viewModel.childInfoState.collectAsState()
    val monthlyChargesState by viewModel.monthlyChargesState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    val titleText = when (val state = childInfoState) {
                        is ChildInfoUiState.Success -> state.childDetails.fullName
                        is ChildInfoUiState.Error -> "Ошибка данных ребенка"
                        else -> "Данные ребенка..."
                    }
                    Text(text = titleText)
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад")
                    }
                },
                actions = {
                    IconButton(onClick = {
                        viewModel.loadChildDetails()
                        viewModel.loadMonthlyCharges()
                    }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Обновить")
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(bottom = 16.dp, top = 8.dp)
        ) {

            item {
                when (val state = childInfoState) {
                    is ChildInfoUiState.Loading -> CenteredCircularProgress()
                    is ChildInfoUiState.Success -> ChildInfoCard(childDetails = state.childDetails)
                    is ChildInfoUiState.Error -> ErrorSection(message = state.message, onRetry = { viewModel.loadChildDetails() })
                }
            }


            when (val chargesStateValue = monthlyChargesState) {
                is MonthlyChargesUiState.Loading -> {
                    item {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Text("История ежемесячных расчетов", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(bottom = 8.dp))
                            Divider()
                            CenteredCircularProgress()
                        }
                    }
                }
                is MonthlyChargesUiState.Success -> {

                    item {
                        Text("История ежемесячных расчетов", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(bottom = 8.dp))
                        Divider()
                    }

                    if (chargesStateValue.charges.isEmpty()) {
                        item {
                            Text(
                                "История расчетов пуста.",
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 16.dp),
                                textAlign = TextAlign.Center,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    } else {

                        items(chargesStateValue.charges, key = { it.id }) { charge ->
                            MonthlyChargeItemRow(charge = charge)

                        }
                    }
                }
                is MonthlyChargesUiState.Error -> {
                    item {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Text("История расчетов начислений", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(bottom = 8.dp))
                            Divider()
                            ErrorSection(message = chargesStateValue.message, onRetry = { viewModel.loadMonthlyCharges() })
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChildInfoCard(childDetails: ChildDetailResponseDto) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Основная информация", style = MaterialTheme.typography.titleMedium)
            Divider()

            InfoRow("ФИО:", childDetails.fullName)
            val birthDateFormatted = try {
                LocalDate.parse(childDetails.birthDate).format(DateTimeFormatter.ofLocalizedDate(FormatStyle.LONG).withLocale(Locale("ru")))
            } catch (e: Exception) { childDetails.birthDate }
            InfoRow("Дата рождения:", birthDateFormatted)

            childDetails.group?.name?.let { InfoRow("Группа:", it) }
            childDetails.address?.let { InfoRow("Адрес:", it) }
            childDetails.medicalInfo?.let { InfoRow("Мед. инфо:", it, isSensitive = true) }


        }
    }
}

@Composable
fun InfoRow(label: String, value: String?, isSensitive: Boolean = false) {
    if (value.isNullOrBlank()) return

    Row(modifier = Modifier.padding(vertical = 2.dp)) {
        Text(
            text = "$label ",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.width(120.dp)
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
fun CenteredCircularProgress() {
    Box(modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
fun ErrorSection(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(Icons.Filled.Warning, contentDescription = "Ошибка", tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(36.dp))
        Text(message, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
        Button(onClick = onRetry, modifier = Modifier.padding(top = 8.dp)) {
            Text("Попробовать снова")
        }
    }
}




@Composable
fun MonthlyChargeItemRow(charge: MonthlyChargeDto) {


    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${getMonthName(charge.month)} ${charge.year}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "%.2f руб.".format(charge.amountDue),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,

                color = MaterialTheme.colorScheme.primary
            )
        }
        Text(
            text = "Рассчитано: ${formatDateTime(charge.calculatedAt)}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp)
        )

        Divider(modifier = Modifier.padding(top = 8.dp))
    }


}

