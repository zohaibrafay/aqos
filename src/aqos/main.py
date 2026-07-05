"""
AQOS Main Entry Point
"""

from aqos.core import Bootstrap
from aqos.version import Version


def main() -> None:
    """
    Main entry point for AQOS.
    """

    bootstrap = Bootstrap()

    try:
        bootstrap.initialize()

        logger = bootstrap.logger
        config = bootstrap.get_configuration()

        logger.info("")
        logger.info(Version.get_banner())
        logger.info("")
        logger.info("AQOS started successfully.")
        logger.info("Environment : %s", config.get("app.environment"))
        logger.info("Log Level   : %s", config.get("logging.level"))
        logger.info("AQOS is ready.")

    except Exception as error:
        if bootstrap.logger:
            bootstrap.logger.exception(
                "AQOS failed to start: %s",
                error,
            )
        else:
            print(f"AQOS failed to start: {error}")

        raise

    finally:
        bootstrap.shutdown()


if __name__ == "__main__":
    main()