package com.getfitwithus.app.otp

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.whatsapp.otp.android.sdk.WhatsAppOtpHandler
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * Flutter <-> Android bridge for the WhatsApp zero-tap OTP flow.
 *
 * MethodChannel "com.getfitwithus.app/whatsapp_otp":
 *  - startHandshake — sends the OTP_REQUESTED handshake broadcast to the
 *    installed WhatsApp client(s) and records the returned request id in
 *    [WhatsAppOtpBus]. Must run right before the app asks the backend to send
 *    the OTP message (WhatsApp honours zero-tap only within the handshake
 *    window). Returns {"supported": Boolean}.
 *  - isHandshakeSupported — probe without starting a handshake.
 *
 * EventChannel "com.getfitwithus.app/whatsapp_otp/events": success events carry
 * the OTP code string from validated zero-tap broadcasts.
 */
object WhatsAppOtpChannels {

    private const val METHOD_CHANNEL = "com.getfitwithus.app/whatsapp_otp"
    private const val EVENT_CHANNEL = "com.getfitwithus.app/whatsapp_otp/events"

    private val mainHandler = Handler(Looper.getMainLooper())

    fun register(messenger: BinaryMessenger, context: Context) {
        val appContext = context.applicationContext
        val otpHandler = WhatsAppOtpHandler()

        MethodChannel(messenger, METHOD_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startHandshake" -> {
                    val requestId = otpHandler.sendOtpIntentToWhatsApp(appContext)
                    WhatsAppOtpBus.beginHandshake(requestId.toString())
                    result.success(
                        mapOf(
                            "supported" to
                                otpHandler.isWhatsAppOtpHandshakeSupported(appContext),
                        ),
                    )
                }
                "isHandshakeSupported" -> result.success(
                    otpHandler.isWhatsAppOtpHandshakeSupported(appContext),
                )
                else -> result.notImplemented()
            }
        }

        EventChannel(messenger, EVENT_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                var sink: EventChannel.EventSink? = null

                val listener: (String) -> Unit = { code ->
                    mainHandler.post { sink?.success(code) }
                }

                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    sink = events
                    WhatsAppOtpBus.subscribe(listener)
                }

                override fun onCancel(arguments: Any?) {
                    WhatsAppOtpBus.unsubscribe(listener)
                    sink = null
                }
            },
        )
    }
}
