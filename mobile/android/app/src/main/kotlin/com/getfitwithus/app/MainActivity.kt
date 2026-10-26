package com.getfitwithus.app

import com.getfitwithus.app.otp.WhatsAppOtpChannels
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        WhatsAppOtpChannels.register(flutterEngine.dartExecutor.binaryMessenger, applicationContext)
    }
}
