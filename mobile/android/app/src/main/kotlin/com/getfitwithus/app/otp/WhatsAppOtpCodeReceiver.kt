package com.getfitwithus.app.otp

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.whatsapp.otp.android.sdk.WhatsAppOtpIncomingIntentHandler

/**
 * Receives zero-tap OTP code broadcasts from WhatsApp (action
 * [ACTION_OTP_RETRIEVED]) and forwards validated codes to the running Flutter
 * UI via [WhatsAppOtpBus]. Declared exported in AndroidManifest.xml — WhatsApp
 * sends the broadcast from outside this app.
 *
 * Codes are validated with Meta's OTP Android SDK against the handshake id
 * recorded by the most recent startHandshake call; broadcasts without a
 * matching handshake are ignored.
 */
class WhatsAppOtpCodeReceiver : BroadcastReceiver() {

    private val incomingHandler = WhatsAppOtpIncomingIntentHandler()

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent == null || intent.action != ACTION_OTP_RETRIEVED) return

        val expectedHandshakeId = WhatsAppOtpBus.handshakeId
        if (expectedHandshakeId == null) {
            Log.w(TAG, "Code broadcast ignored: no zero-tap handshake was started")
            return
        }

        incomingHandler.processOtpCode(
            intent,
            expectedHandshakeId,
            { code -> WhatsAppOtpBus.publish(code) },
            { error, e -> Log.w(TAG, "Code broadcast rejected: $error", e) },
        )
    }

    companion object {
        private const val TAG = "WhatsAppOtpReceiver"

        /** Action WhatsApp broadcasts the OTP code with (Meta OTP Android SDK). */
        const val ACTION_OTP_RETRIEVED = "com.whatsapp.otp.OTP_RETRIEVED"
    }
}
