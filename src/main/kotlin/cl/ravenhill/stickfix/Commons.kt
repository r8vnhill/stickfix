package cl.ravenhill.stickfix

import mu.KotlinLogging
import java.io.File

internal val STICKFIX_ROOT by lazy {
  val env = "STICKFIX_PATH"
  val path = System.getenv(env)
  if (path != null){
    File(System.getenv(env))
} else {
  throw StickfixEnvException(env)
  }
}

internal val DATABASE_ROOT by lazy { File(STICKFIX_ROOT, "data").also(File::mkdirs) }

internal val logger = KotlinLogging.logger {}

