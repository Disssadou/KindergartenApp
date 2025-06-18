package com.yourdomain.kindergartenmobileapp.data.network.dto
import com.google.gson.annotations.SerializedName

data class ChildParentAssociationDto(
    @SerializedName("child_id") val childId: Int,
    @SerializedName("parent_id") val parentId: Int,
    @SerializedName("relation_type") val relationType: String,
    @SerializedName("child") val child: ChildSimpleDto,
    @SerializedName("parent") val parent: UserSimpleDto
)
