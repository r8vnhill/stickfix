package cl.ravenhill.stickfix.commands

import cl.ravenhill.stickfix.STICKFIX_ROOT
import cl.ravenhill.stickfix.StickfixBot
import com.github.kotlintelegrambot.dispatcher.Dispatcher
import java.io.File


private val MESSAGES_ROOT by lazy { File(STICKFIX_ROOT, "messages").also(File::mkdirs) }
internal val HELP_MESSAGE by lazy { File(MESSAGES_ROOT, "help.md").readText() }

internal const val START = "start"
internal const val HELP = "help"
internal const val FORGET_ME = "forgetMe"

/**
 * Bounds the dispatcher with a command handler.
 *
 * @param dispatcher
 *    the bot dispatcher.
 * @param handler
 *    a function that registers a new handler to the dispatcher.
 */
fun bind(dispatcher: Dispatcher, handler: (Dispatcher, StickfixBot) -> Unit, context: StickfixBot) {
  handler(dispatcher, context)
}
