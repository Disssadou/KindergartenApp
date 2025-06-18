package com.yourdomain.kindergartenmobileapp.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.yourdomain.kindergartenmobileapp.R
import com.yourdomain.kindergartenmobileapp.data.network.dto.PostDto
import java.time.LocalDateTime
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PostItemView(
    post: PostDto,
    onPostClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onPostClick,
        modifier = modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column {

            if (post.mediaFiles.isNotEmpty()) {
                val firstMedia = post.mediaFiles[0]
                if (firstMedia.fileType.equals("photo", ignoreCase = true) || firstMedia.fileType.equals("image", ignoreCase = true) ) {
                    val imageUrl = firstMedia.thumbnailPath?.let { thumbPath ->

                        "http://10.0.2.2:8000/uploads/post_media/${thumbPath.trimStart('/')}"
                    }

                    if (imageUrl != null) {
                        AsyncImage(
                            model = ImageRequest.Builder(LocalContext.current)
                                .data(imageUrl)
                                .crossfade(true)

                                .build(),
                            contentDescription = post.title ?: "Изображение к посту",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(180.dp)
                                .clip(MaterialTheme.shapes.medium),
                            contentScale = ContentScale.Crop
                        )
                    }
                }
            }

            Column(modifier = Modifier.padding(12.dp)) {
                if (post.isPinned) {
                    Text(
                        text = "📌 ЗАКРЕПЛЕНО",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(bottom = 4.dp)
                    )
                }
                post.title?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = post.textContent,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {



                    val formattedDate = try {
                        val zdt = ZonedDateTime.parse(post.createdAt)
                        zdt.withZoneSameInstant(java.time.ZoneId.systemDefault())
                            .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT))
                    } catch (e: Exception) {
                        post.createdAt.take(10)
                    }
                    Text(formattedDate, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}