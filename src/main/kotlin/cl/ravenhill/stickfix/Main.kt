package cl.ravenhill.stickfix

import kotlinx.cli.ArgParser
import kotlinx.cli.ArgType
import kotlinx.cli.default

fun main(args: Array<String>) {
  val parser = ArgParser("Stickfix")
  val test by parser.option(ArgType.Boolean).default(false)
  parser.parse(args)
  val tokenEnvPath = if (test) "TELEGRAM_TEST_TOKEN" else "STICKFIX_TOKEN"
  StickfixBot(System.getenv(tokenEnvPath) ?: throw StickfixEnvException(tokenEnvPath)).run()
}