package com.yourdomain.kindergartenmobileapp.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.EventAvailable
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.yourdomain.kindergartenmobileapp.data.network.dto.NotificationDto
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale


object NotificationDisplayHelper {

    val AUDIENCE_DISPLAY_MAP: Map<String, String> = mapOf(
        "all" to "Всем пользователям",
        "parents" to "Только родителям",
        "teachers" to "Только воспитателям"

    )
}


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationListItem(
    notification: NotificationDto,
    onNotificationClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onNotificationClick,
        modifier = modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (notification.isEvent) Icons.Filled.EventAvailable else Icons.Filled.Campaign,
                contentDescription = if (notification.isEvent) "Событие" else "Уведомление",
                tint = if (notification.isEvent) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(36.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = notification.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = notification.content,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {

                    val audienceDisplayValue: String = notification.audienceRaw?.let { rawAudience ->
                        NotificationDisplayHelper.AUDIENCE_DISPLAY_MAP[rawAudience.lowercase()]
                            ?: rawAudience.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }
                    } ?: "Аудитория не указана"

                    Text(audienceDisplayValue, style = MaterialTheme.typography.labelSmall)


                    val formattedDate = try {

                        val zdt = ZonedDateTime.parse(notification.createdAt)
                        zdt.withZoneSameInstant(java.time.ZoneId.systemDefault())
                            .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.SHORT))
                    } catch (e: Exception) {
                        notification.createdAt.take(10)
                    }
                    Text(formattedDate, style = MaterialTheme.typography.labelSmall)
                }

                if (notification.isEvent && !notification.eventDate.isNullOrBlank()) {
                    val formattedEventDate = try {
                        val zdt = ZonedDateTime.parse(notification.eventDate)
                        zdt.withZoneSameInstant(java.time.ZoneId.systemDefault())
                            .format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
                    } catch (e: Exception) {
                        notification.eventDate?.take(16) ?: ""
                    }
                    Text(
                        "Дата события: $formattedEventDate",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.tertiary,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                }
            }
        }
    }
}