package cl.ravenhill.stickfix

import mu.KotlinLogging
import java.io.File

internal val STICKFIX_ROOT = File(System.getenv("STICKFIX_PATH"))
internal val DATABASE_ROOT = File(STICKFIX_ROOT, "data").also {
  it.mkdirs()
}

internal val logger = KotlinLogging.logger {}

object Commands {
  const val START = "start"
}