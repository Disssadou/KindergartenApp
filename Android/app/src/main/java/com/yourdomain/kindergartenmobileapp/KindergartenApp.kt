package com.yourdomain.kindergartenmobileapp

import android.app.Application
import android.util.Log
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

@HiltAndroidApp
class KindergartenApp : Application() {

    override fun onCreate() {
        super.onCreate()

        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
            Timber.d("Timber initialized for DEBUG build.")
        } else {

            Timber.i("Timber initialized for RELEASE build (minimal logging).")
        }
    }
}