package cl.ravenhill.stickfix.commands

import cl.ravenhill.stickfix.Idle
import cl.ravenhill.stickfix.StickfixBot
import cl.ravenhill.stickfix.StickfixMessageException
import cl.ravenhill.stickfix.data.Users
import cl.ravenhill.stickfix.logger
import com.github.kotlintelegrambot.dispatcher.Dispatcher
import com.github.kotlintelegrambot.dispatcher.command
import com.github.kotlintelegrambot.entities.ChatId
import com.github.kotlintelegrambot.entities.ParseMode
import java.io.FileNotFoundException


/**
 * Answers the `/start` command with a hello sticker.
 * @param dispatcher
 *    the receiver of the update
 */
fun start(dispatcher: Dispatcher, context: StickfixBot) {
  dispatcher.command(START) {
    context.state = Idle(context)
    val id = message.chat.id
    if (id in Users) {
      logger.info { "User $id already in the database." }
    } else {
      logger.info { "User $id is not on the database." }
      Users.add(id)
      logger.info { "$id added to Users." }
    }
    @Suppress("SpellCheckingInspection")
    val fogsHelloSticker = "CAADBAADTAADqAABTgXzVqN6dJUIXwI"
    bot.sendSticker(
      chatId = ChatId.fromId(id),
      sticker = fogsHelloSticker,
      disableNotification = false,
      replyToMessageId = null,
      allowSendingWithoutReply = false,
      replyMarkup = null
    )
  }
}

/**
 * Answers the `/help` command with the help message defined in the
 * [``help.md``](messages/help.md) file.
 *
 * @param dispatcher
 *    the receiver of the update
 * @throws StickfixMessageException
 *    if the ``help.md`` file cannot be found.
 */
@Throws(StickfixMessageException::class)
fun help(dispatcher: Dispatcher, context: StickfixBot) {
  dispatcher.command(HELP) {
    context.state = Idle(context)
    val id = ChatId.fromId(message.chat.id)
    try {
      bot.sendMessage(chatId = id, HELP_MESSAGE, ParseMode.MARKDOWN)
      logger.info { "Help message sent to ${message.chat.username} ($id)." }
    } catch (e: FileNotFoundException) {
      bot.sendMessage(chatId = id, "I can't help you rn due to an unexpected error uwu")
      throw StickfixMessageException("help", e)
    }
  }
}