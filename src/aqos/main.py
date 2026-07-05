from aqos.version import Version
from aqos.core.configuration import ConfigurationManager


def main():

    print(Version.get_banner())

    config = ConfigurationManager()

    config.load()

    config.validate()

    print()

    print("Configuration Loaded")

    print(f"Environment : {config.get('app.environment')}")

    print(f"Log Level   : {config.get('logging.level')}")

    print()

    print("AQOS Ready")


if __name__ == "__main__":

    main()