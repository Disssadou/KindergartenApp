package com.yourdomain.kindergartenmobileapp.data.repository

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.yourdomain.kindergartenmobileapp.domain.repository.TokenRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton


private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "kinder_settings_prefs")

@Singleton
class TokenRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context
) : TokenRepository {

    private object PreferencesKeys {
        val AUTH_TOKEN = stringPreferencesKey("auth_token")
        val REMEMBER_ME = booleanPreferencesKey("remember_me")
        val LAST_USERNAME = stringPreferencesKey("last_username")
    }

    override suspend fun saveToken(token: String) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.AUTH_TOKEN] = token
        }
    }


    override suspend fun getToken(): String? {
        return try {
            val preferences = context.dataStore.data
                .catch { exception ->
                    if (exception is IOException) {
                        emit(emptyPreferences())
                    } else {
                        throw exception
                    }
                }.first()
            preferences[PreferencesKeys.AUTH_TOKEN]
        } catch (e: Exception) {

            null
        }
    }




    override suspend fun clearToken() {
        context.dataStore.edit { preferences ->
            preferences.remove(PreferencesKeys.AUTH_TOKEN)
        }
    }

    override suspend fun saveRememberMe(remember: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.REMEMBER_ME] = remember
        }
    }

    override suspend fun shouldRememberMe(): Boolean {
        return try {
            context.dataStore.data.first()[PreferencesKeys.REMEMBER_ME] ?: false
        } catch (e: Exception) { false }
    }

    override suspend fun saveLastUsername(username: String) {
        context.dataStore.edit { preferences ->
            preferences[PreferencesKeys.LAST_USERNAME] = username
        }
    }

    override suspend fun getLastUsername(): String? {
        return try {
            context.dataStore.data.first()[PreferencesKeys.LAST_USERNAME]
        } catch (e: Exception) { null }
    }

    override suspend fun clearLoginCredentials() {
        context.dataStore.edit { preferences ->
            preferences.remove(PreferencesKeys.AUTH_TOKEN)
            preferences.remove(PreferencesKeys.REMEMBER_ME)
            preferences.remove(PreferencesKeys.LAST_USERNAME)
        }
    }
}