package com.example.amishopengine

import android.content.Context

class SessionManager(context: Context) {
    private val prefs = context.getSharedPreferences("ire_prefs", Context.MODE_PRIVATE)

    fun getOrCreate(): String {
        var id = prefs.getString("session_id", null)
        if (id == null) {
            id = "IRE-" + (1..8).map { ('A'..'Z').random() }.joinToString("")
            prefs.edit().putString("session_id", id).apply()
        }
        return id
    }

    fun set(id: String) = prefs.edit().putString("session_id", id).apply()
    fun get(): String = prefs.getString("session_id", "") ?: ""
}
