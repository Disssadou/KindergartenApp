package com.yourdomain.kindergartenmobileapp.data.network.dto

import com.google.gson.annotations.SerializedName



data class MediaDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("file_path")
    val filePath: String,
    @SerializedName("thumbnail_path")
    val thumbnailPath: String?,
    @SerializedName("original_filename")
    val originalFilename: String,
    @SerializedName("mime_type")
    val mimeType: String,
    @SerializedName("file_type")
    val fileType: String
)

data class PostDto(
    @SerializedName("id")
    val id: Int,
    @SerializedName("title")
    val title: String?,
    @SerializedName("text_content")
    val textContent: String,
    @SerializedName("author_id")
    val authorId: Int?,

    @SerializedName("is_pinned")
    val isPinned: Boolean,
    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String,
    @SerializedName("media_files")
    val mediaFiles: List<MediaDto> = emptyList()
)