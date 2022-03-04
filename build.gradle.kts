import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import java.net.URI

plugins {
  kotlin("jvm") version "1.6.10"
  application
}

group = "cl.ravenhill"
version = "3.0"

repositories {
  mavenCentral()
  maven { url = URI("https://jitpack.io") }
}

dependencies {
  implementation(
    group = "io.github.kotlin-telegram-bot.kotlin-telegram-bot",
    name = "telegram",
    version = "6.0.6"
  )
  implementation(group = "org.jetbrains.kotlinx", name = "kotlinx-cli", version = "0.3.4")
  implementation(group = "org.jetbrains.exposed", name = "exposed-core", version = "0.37.3")
  implementation(group = "org.jetbrains.exposed", name = "exposed-dao", version = "0.37.3")
  implementation(group = "org.jetbrains.exposed", name = "exposed-jdbc", version = "0.37.3")
  implementation(group = "org.xerial", name = "sqlite-jdbc", version = "3.30.1")
  implementation(group = "io.github.microutils", name = "kotlin-logging", version = "2.1.21")
  runtimeOnly(group = "ch.qos.logback", name = "logback-classic", version = "1.3.0-alpha13")
  testImplementation(group = "org.junit.jupiter", name = "junit-jupiter-api", version = "5.8.2")
  testRuntimeOnly(group = "org.junit.jupiter", name = "junit-jupiter-engine", version = "5.8.2")
}

tasks.test {
  useJUnitPlatform()
}

tasks.withType<KotlinCompile> {
  kotlinOptions.jvmTarget = "13"
}

application {
  mainClass.set("MainKt")
}