package com.yourdomain.kindergartenmobileapp.di

import com.yourdomain.kindergartenmobileapp.data.repository.TokenRepositoryImpl
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindTokenRepository(
        tokenRepositoryImpl: TokenRepositoryImpl
    ): TokenRepository
}