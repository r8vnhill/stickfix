package cl.ravenhill.stickfix

import cl.ravenhill.stickfix.commands.bind
import cl.ravenhill.stickfix.commands.forgetMe
import cl.ravenhill.stickfix.commands.help
import cl.ravenhill.stickfix.commands.start
import cl.ravenhill.stickfix.data.DbDriver
import com.github.kotlintelegrambot.Bot
import com.github.kotlintelegrambot.bot
import com.github.kotlintelegrambot.dispatch
import com.github.kotlintelegrambot.dispatcher.Dispatcher
import com.github.kotlintelegrambot.dispatcher.text
import com.github.kotlintelegrambot.logging.LogLevel
import kotlinx.cli.ArgParser
import kotlinx.cli.ArgType
import kotlinx.cli.default

fun main(args: Array<String>) {
  val parser = ArgParser("Stickfix")
  val test by parser.option(ArgType.Boolean).default(false)
  parser.parse(args)
  val tokenEnvPath = if (test) "TELEGRAM_TEST_TOKEN" else "STICKFIX_TOKEN"
  val stickfix = StickfixBot(tokenEnvPath)
  stickfix.run()
}

class StickfixBot(tokenEnvPath: String) {
  private val bot: Bot
  internal var state: StickfixState = Idle(this)

  init {
    DbDriver.start()
    bot = bot {
      token = System.getenv(tokenEnvPath) ?: throw StickfixEnvException(tokenEnvPath)
      logLevel = LogLevel.Error
      dispatch {
        registerCommands(this)
      }
    }
  }

  private fun registerCommands(dispatcher: Dispatcher) {
    with(dispatcher) {
      registerCommand(::start, this@StickfixBot)
      registerCommand(::help, this@StickfixBot)
      registerCommand(::forgetMe, this@StickfixBot)
      text {
        this@StickfixBot.state.accept(this.text)
      }
    }
  }

  fun run() {
    logger.info { "Running bot polling service..." }
    bot.startPolling()
  }
}

private fun Dispatcher.registerCommand(
  handler: (Dispatcher, StickfixBot) -> Unit,
  context: StickfixBot
) {
  bind(this, handler, context)
}