package com.getfitwithus.app.otp

import java.util.concurrent.CopyOnWriteArrayList

/**
 * Process-wide state for WhatsApp zero-tap OTP delivery.
 *
 * The handshake id lives here rather than on the Dart side so the
 * manifest-registered receiver can validate an incoming code broadcast even
 * while the Flutter UI is navigating. [latestCode] buffers the most recent
 * validated code so a subscriber that attaches just after the broadcast
 * (e.g. the OTP screen finishing navigation) still receives it.
 */
object WhatsAppOtpBus {

    /** Correlation id from the most recent handshake, or null before the first one. */
    @Volatile
    var handshakeId: String? = null
        private set

    /** Most recent code that passed handshake validation, or null. */
    @Volatile
    var latestCode: String? = null
        private set

    private val listeners = CopyOnWriteArrayList<(String) -> Unit>()

    /** Records a fresh handshake; any buffered code from an earlier request is dropped. */
    fun beginHandshake(id: String) {
        synchronized(this) {
            handshakeId = id
            latestCode = null
        }
    }

    /** Publishes a validated code to current subscribers and buffers it for late ones. */
    fun publish(code: String) {
        synchronized(this) {
            latestCode = code
            listeners.forEach { it(code) }
        }
    }

    /** Subscribes to codes; a buffered code is delivered immediately on subscribe. */
    fun subscribe(listener: (String) -> Unit) {
        synchronized(this) {
            latestCode?.let(listener)
            listeners.add(listener)
        }
    }

    fun unsubscribe(listener: (String) -> Unit) {
        listeners.remove(listener)
    }

    /** Clears all state; used by unit tests to start from a clean slate. */
    fun reset() {
        synchronized(this) {
            handshakeId = null
            latestCode = null
            listeners.clear()
        }
    }
}
