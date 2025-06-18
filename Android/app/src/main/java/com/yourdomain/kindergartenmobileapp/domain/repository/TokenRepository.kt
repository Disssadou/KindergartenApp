package com.yourdomain.kindergartenmobileapp.domain.repository

interface TokenRepository {
    suspend fun saveToken(token: String)
    suspend fun getToken(): String?
    suspend fun clearToken()

    suspend fun saveRememberMe(remember: Boolean)
    suspend fun shouldRememberMe(): Boolean
    suspend fun saveLastUsername(username: String)
    suspend fun getLastUsername(): String?
    suspend fun clearLoginCredentials()
}