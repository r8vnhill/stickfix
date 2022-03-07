package cl.ravenhill.stickfix.commands

import cl.ravenhill.stickfix.StickfixBot
import cl.ravenhill.stickfix.WaitingForgetMeConfirmation
import com.github.kotlintelegrambot.Bot
import com.github.kotlintelegrambot.dispatcher.Dispatcher
import com.github.kotlintelegrambot.dispatcher.command
import com.github.kotlintelegrambot.entities.ChatId
import com.github.kotlintelegrambot.entities.KeyboardReplyMarkup
import com.github.kotlintelegrambot.entities.ParseMode
import com.github.kotlintelegrambot.entities.keyboard.KeyboardButton
import mu.KotlinLogging

private val logger by lazy { KotlinLogging.logger {} }

/**
 * Answers the ``/forgetMe`` command and removes the user that sent the message from the database.
 *
 * @param dispatcher the receiver of the update.
 */
fun forgetMe(dispatcher: Dispatcher, context: StickfixBot) {
  dispatcher.command(FORGET_ME) {
    context.state = WaitingForgetMeConfirmation(context)
    val id = ChatId.fromId(message.chat.id)
    bot.sendMessages(id, "This will remove all of your *private packs*.")
    val keyboard =
      KeyboardReplyMarkup(
        KeyboardButton("Yes"),
        KeyboardButton("No"),
        oneTimeKeyboard = true,
        resizeKeyboard = true
      )
    bot.sendMessage(
      id,
      text = "Are you sure you want me to remove you from the Database?",
      replyMarkup = keyboard
    )
//    val username = message.chat.username
//    if (Users.remove(id.toLong())) {
//      logger.info { "User $username ($id) removed from database." }
//    } else {
//      logger.warn { "User $username ($id) is not on the database." }
//    }
//    bot.sendMessage(chatId = id, "Ok uwu")
  }
}

private fun Bot.sendMessages(id: ChatId.Id, vararg messages: String) {
  for (message in messages) {
    sendMessage(id, message, ParseMode.MARKDOWN)
  }
}

private fun ChatId.Id.toLong() = id

