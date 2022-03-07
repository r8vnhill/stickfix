package cl.ravenhill.stickfix.logging

import ch.qos.logback.classic.Level
import cl.ravenhill.stickfix.STICKFIX_ROOT
import org.slf4j.LoggerFactory
import java.io.File
import kotlin.reflect.KClass
import ch.qos.logback.classic.Logger as JLogger

private val LOG_DIR by lazy { File(STICKFIX_ROOT, "logs").also(File::mkdirs) }

class Logger private constructor(
  private val logger: JLogger,
  logLevel: Level,
  appenderList: MutableList<Appender>
) {

  init {
    logger.level = logLevel
    appenderList.forEach {
      it.getAppender().start()
      logger.addAppender(it.getAppender())
    }
  }

  class Builder {
    internal var klass: KClass<*> = Logger::class
    lateinit var logLevel: Level
    val appenderList = mutableListOf<Appender>()

    fun build(body: Builder.() -> Unit): Logger {
      body()
      return build()
    }

    private fun build(): Logger {
      return Logger(LoggerFactory.getLogger(klass.java) as JLogger, logLevel, appenderList)
    }
  }

  fun info(message: () -> String) {
    logger.info(message())
  }
}

fun buildLogger(body: Logger.Builder.() -> Unit): Logger = Logger.Builder().build(body)

fun defaultLogger(klass: KClass<*>) = buildLogger {
  this.klass = klass
  logLevel = Level.DEBUG
  consoleAppender("STDOUT") {
    pattern { "%d{HH:mm} %-5level %logger{36} - %msg%n" }
  }
  fileAppender("FILE", File(LOG_DIR, "stickfix.log")) {
    pattern { "%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n" }
  }
}

private fun Logger.Builder.fileAppender(
  name: String,
  logFile: File,
  appenderConfiguration: FileAppender.() -> Unit
) {
  this.registerAppender(FileAppender(name, logFile).apply(appenderConfiguration))
}

private fun Logger.Builder.consoleAppender(
  name: String,
  appenderConfiguration: ConsoleAppender.() -> Unit
) {
  this.registerAppender(ConsoleAppender(name).apply(appenderConfiguration))
}

private fun Logger.Builder.registerAppender(appender: Appender) {
  appenderList.add(appender)
}

