package cl.ravenhill.stickfix

/**
 * Error raised when Stickfix can't access an environment variable.
 */
class StickfixEnvException(variable: String) :
  Exception("$variable is not defined in the current environment")