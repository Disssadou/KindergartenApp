package com.yourdomain.kindergartenmobileapp.data.network.interceptor

import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import kotlinx.coroutines.runBlocking // Убедитесь, что импортирован
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenRepository: TokenRepository
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val requestBuilder = originalRequest.newBuilder()


        val token = runBlocking {
            tokenRepository.getToken()
        }

        if (!token.isNullOrBlank() && !originalRequest.url.encodedPath.contains("api/auth/token")) {
            requestBuilder.header("Authorization", "Bearer $token")
        }

        val request = requestBuilder.build()
        return chain.proceed(request)
    }
}