package cl.ravenhill.stickfix

class StickfixEnvException(private val variable: String) :
  Exception("$variable is not defined in the current environment")