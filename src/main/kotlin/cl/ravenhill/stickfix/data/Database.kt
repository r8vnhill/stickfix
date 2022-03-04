package cl.ravenhill.stickfix.data

import cl.ravenhill.stickfix.DATABASE_ROOT
import org.jetbrains.exposed.dao.Entity
import org.jetbrains.exposed.dao.EntityClass
import org.jetbrains.exposed.dao.id.EntityID
import org.jetbrains.exposed.dao.id.LongIdTable
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.TransactionManager
import org.jetbrains.exposed.sql.transactions.transaction
import java.sql.Connection

internal object DbDriver {
  fun start() {
    Database.connect("jdbc:sqlite:$DATABASE_ROOT/data.db", "org.sqlite.JDBC")
    TransactionManager.manager.defaultIsolationLevel = Connection.TRANSACTION_SERIALIZABLE
    transaction { SchemaUtils.create(Users) }
  }
}

internal object Users : LongIdTable() {
  operator fun contains(id: Long) = transaction {
    addLogger(StdOutSqlLogger)
    User.findById(id) != null
  }

  /**
   * Creates a new user in the Database.
   *
   * @param id
   *    the user's id.
   */
  fun add(id: Long) {
    transaction {
      User.new(id) {
      }
      commit()
    }
  }
}

private fun <T> SizedIterable<T>.notEmpty() = !this.empty()

internal class User(id: EntityID<Long>) : Entity<Long>(id) {
  companion object : EntityClass<Long, User>(Users)
}