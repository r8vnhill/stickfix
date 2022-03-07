package cl.ravenhill.stickfix.logging

import ch.qos.logback.classic.LoggerContext
import ch.qos.logback.classic.encoder.PatternLayoutEncoder
import ch.qos.logback.classic.spi.ILoggingEvent
import ch.qos.logback.core.OutputStreamAppender
import org.slf4j.LoggerFactory
import java.io.File
import ch.qos.logback.core.ConsoleAppender as JConsoleAppender
import ch.qos.logback.core.FileAppender as JFileAppender

interface Appender {
  fun getAppender(): OutputStreamAppender<ILoggingEvent>

  fun pattern(body: () -> String) {
    val appender = getAppender()
    appender.encoder = PatternLayoutEncoder().also {
      it.pattern = body()
      it.context = appender.context
      it.start()
    }
  }
}

abstract class AbstractAppender(protected open val name: String) : Appender {
  protected open fun setupAppender(appender: OutputStreamAppender<ILoggingEvent>) {
    appender.name = name
    appender.context = LoggerFactory.getILoggerFactory() as LoggerContext
  }
}

class ConsoleAppender(override val name: String) : AbstractAppender(name) {
  private val appender = JConsoleAppender<ILoggingEvent>().also(::setupAppender)

  override fun getAppender() = appender
}

class FileAppender(override val name: String, private val logFile: File) : AbstractAppender(name) {
  private val appender = JFileAppender<ILoggingEvent>().also(::setupAppender)

  override fun getAppender() = appender

  private fun setupAppender(appender: JFileAppender<ILoggingEvent>) {
    super.setupAppender(appender)
    appender.file = logFile.absolutePath
  }
}