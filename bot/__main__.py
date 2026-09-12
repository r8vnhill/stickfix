"""Container-friendly Stickfix entry point."""

from bot.config import load_config
from bot.stickfix import Stickfix


def main() -> None:
  config = load_config()
  Stickfix(config.token, database_url=config.database_url).run()


if __name__ == "__main__":
  main()
