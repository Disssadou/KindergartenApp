    package com.yourdomain.kindergartenmobileapp.data.network.api

    import com.yourdomain.kindergartenmobileapp.data.network.dto.TokenResponse
    import com.yourdomain.kindergartenmobileapp.data.network.dto.UserResponse
    import com.yourdomain.kindergartenmobileapp.data.network.dto.GroupDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.AttendanceRecordDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.BulkAttendanceCreateDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.MealMenuDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.PostDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.NotificationDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildParentAssociationDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.ChildDetailResponseDto
    import com.yourdomain.kindergartenmobileapp.data.network.dto.MonthlyChargeDto
    import retrofit2.http.Query
    import retrofit2.Response
    import retrofit2.http.Field
    import retrofit2.http.FormUrlEncoded
    import retrofit2.http.GET
    import retrofit2.http.Header
    import retrofit2.http.POST
    import retrofit2.http.Body
    import retrofit2.http.Path


    interface AuthApiService {

        @FormUrlEncoded
        @POST("api/auth/token")
        suspend fun login(
            @Field("username") username: String,
            @Field("password") password: String,

        ): Response<TokenResponse>

        @GET("api/auth/me")
        suspend fun getCurrentUser(

        ): Response<UserResponse>

        @GET("api/groups/")
        suspend fun getGroupsForTeacher(
            @Query("teacher_id") teacherId: Int,
            @Query("skip") skip: Int = 0,
            @Query("limit") limit: Int = 100
        ): Response<List<GroupDto>>

        @GET("api/children/")
        suspend fun getChildrenForGroup(
            @Query("group_id") groupId: Int,
            @Query("limit") limit: Int = 200
        ): Response<List<ChildDto>>

        @GET("api/attendance/")
        suspend fun getAttendanceRecords(
            @Query("group_id") groupId: Int,
            @Query("attendance_date") date: String
        ): Response<List<AttendanceRecordDto>>

        @POST("api/attendance/bulk")
        suspend fun postBulkAttendance(
            @Body bulkAttendanceData: BulkAttendanceCreateDto
        ): Response<List<AttendanceRecordDto>>

        @GET("api/menus/")
        suspend fun getMealMenus(
            @Query("start_date") startDate: String,
            @Query("end_date") endDate: String
        ): Response<List<MealMenuDto>>

        @GET("api/posts/")
        suspend fun getPosts(
            @Query("skip") skip: Int = 0,
            @Query("limit") limit: Int = 10,
            @Query("pinned_only") pinnedOnly: Boolean? = null
        ): Response<List<PostDto>>

        @GET("api/posts/{postId}")
        suspend fun getPost(@Path("postId") postId: Int): Response<PostDto>

        @GET("api/notifications/")
        suspend fun getNotifications(
            @Query("skip") skip: Int = 0,
            @Query("limit") limit: Int = 20,
            @Query("audience") audience: String? = null,
            @Query("is_event") isEvent: Boolean? = null
        ): Response<List<NotificationDto>>

        @GET("api/users/{userId}/children")
        suspend fun getChildrenForUser(
            @Path("userId") userId: Int
        ): Response<List<ChildParentAssociationDto>>

        @GET("api/children/{childId}")
        suspend fun getChildDetails(
            @Path("childId") childId: Int
        ): Response<ChildDetailResponseDto>

        @GET("api/children/{childId}/monthly-charges")
        suspend fun getMonthlyChargesForChild(
            @Path("childId") childId: Int,
            @Query("year") year: Int? = null
        ): Response<List<MonthlyChargeDto>>


    }