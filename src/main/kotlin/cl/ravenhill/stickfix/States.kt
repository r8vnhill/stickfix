package cl.ravenhill.stickfix

/**
 * Base state.
 * Changes context state to [Idle] for all inputs.
 */
open class StickfixState(private val context: StickfixBot) {
  /**
   * Reads user text messages and updates the state accordingly.
   */
  open fun accept(text: String) {
    context.state = Idle(context)
  }
}

/**
 * The bot is in Idle state when it's not expecting any answer from the user.
 *
 * Behaviour is equivalent to a Null Object Pattern.
 */
class Idle(context: StickfixBot) : StickfixState(context)


class WaitingForgetMeConfirmation(context: StickfixBot) : StickfixState(context) {
  init {

  }
}
