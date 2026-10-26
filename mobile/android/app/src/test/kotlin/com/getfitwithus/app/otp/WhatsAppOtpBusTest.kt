package com.getfitwithus.app.otp

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class WhatsAppOtpBusTest {

    @Before
    fun setUp() = WhatsAppOtpBus.reset()

    @Test
    fun `beginHandshake records the id and clears any buffered code`() {
        WhatsAppOtpBus.beginHandshake("first")
        WhatsAppOtpBus.publish("123456")

        WhatsAppOtpBus.beginHandshake("second")

        assertEquals("second", WhatsAppOtpBus.handshakeId)
        assertNull(WhatsAppOtpBus.latestCode)
    }

    @Test
    fun `publish notifies subscribed listeners and buffers the code`() {
        val received = mutableListOf<String>()
        WhatsAppOtpBus.subscribe(received::add)

        WhatsAppOtpBus.publish("654321")

        assertEquals(listOf("654321"), received)
        assertEquals("654321", WhatsAppOtpBus.latestCode)
    }

    @Test
    fun `late subscriber receives the buffered code once`() {
        val received = mutableListOf<String>()
        WhatsAppOtpBus.publish("111222")

        WhatsAppOtpBus.subscribe(received::add)

        assertEquals(listOf("111222"), received)
    }

    @Test
    fun `unsubscribed listeners stop receiving codes`() {
        val received = mutableListOf<String>()
        val listener: (String) -> Unit = received::add
        WhatsAppOtpBus.subscribe(listener)
        WhatsAppOtpBus.unsubscribe(listener)

        WhatsAppOtpBus.publish("999999")

        assertEquals("no delivery to the removed listener", emptyList<String>(), received)
        assertEquals("999999", WhatsAppOtpBus.latestCode)
    }

    @Test
    fun `reset clears handshake, buffer and listeners`() {
        val received = mutableListOf<String>()
        WhatsAppOtpBus.beginHandshake("id-1")
        WhatsAppOtpBus.subscribe(received::add)
        WhatsAppOtpBus.publish("123123")

        WhatsAppOtpBus.reset()

        assertNull(WhatsAppOtpBus.handshakeId)
        assertNull(WhatsAppOtpBus.latestCode)
        WhatsAppOtpBus.subscribe({ received.add("should-not-fire") })
        assertEquals(listOf("123123"), received)
    }
}
