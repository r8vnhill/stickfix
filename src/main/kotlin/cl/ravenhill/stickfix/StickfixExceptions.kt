package cl.ravenhill.stickfix

import cl.ravenhill.stickfix.data.User

/**
 * Error raised when Stickfix can't access an environment variable.
 */
class StickfixEnvException(variable: String) :
  Exception("$variable is not defined in the current environment")

/**
 * Error raised when Stickfix fails to send a message.
 */
class StickfixMessageException(origin: String, cause: Throwable) :
  Exception("There was an error sending message from <$origin>.", cause)
