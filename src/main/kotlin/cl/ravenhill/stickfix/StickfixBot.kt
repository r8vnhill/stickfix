package cl.ravenhill.stickfix

import cl.ravenhill.stickfix.data.DbDriver
import cl.ravenhill.stickfix.data.User
import cl.ravenhill.stickfix.data.Users
import com.github.kotlintelegrambot.Bot
import com.github.kotlintelegrambot.bot
import com.github.kotlintelegrambot.dispatch
import com.github.kotlintelegrambot.dispatcher.command
import com.github.kotlintelegrambot.entities.ChatId
import com.github.kotlintelegrambot.logging.LogLevel
import org.jetbrains.exposed.sql.StdOutSqlLogger
import org.jetbrains.exposed.sql.addLogger
import org.jetbrains.exposed.sql.select
import org.jetbrains.exposed.sql.transactions.transaction

class StickfixBot(private val token: String) {
  fun run() {
    DbDriver.start()
    val bot = bot {
      token = this@StickfixBot.token
      dispatch {
        command(Commands.START) {
          startMessageHandler(bot, message.chat.id)
        }
      }
    }
    bot.startPolling()
  }

  /**
   * Answers the /start command with a hello sticker and adds the user to the database.
   */
  private fun startMessageHandler(bot: Bot, id: Long) {
    if (id in Users) {
      logger.info { "User $id already in the database." }
    } else {
      Users.add(id)
      logger.info { "User $id not in the database." }
    }
    // AAAAAAAA
    bot.sendSticker(
      chatId = ChatId.fromId(id),
      sticker = "CAADBAADTAADqAABTgXzVqN6dJUIXwI",
      disableNotification = false,
      replyToMessageId = null,
      allowSendingWithoutReply = false,
      replyMarkup = null
    )
  }
}
