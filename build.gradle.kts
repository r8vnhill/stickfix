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
  implementation("io.github.kotlin-telegram-bot.kotlin-telegram-bot:telegram:6.0.6")
  testImplementation("org.junit.jupiter:junit-jupiter-api:5.8.2")
  testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:5.8.2")
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