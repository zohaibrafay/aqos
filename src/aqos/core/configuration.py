"""
AQOS Configuration Manager
"""

from pathlib import Path
import os
import yaml

from dotenv import load_dotenv


class ConfigurationManager:
    """
    Loads AQOS configuration.
    """

    def __init__(self):

        load_dotenv()

        self.environment = os.getenv(
            "AQOS_ENV",
            "development"
        )

        self.root = Path.cwd()

        self.config_dir = self.root / "config"

        self.config = {}

    def load(self):

        file = self.config_dir / f"{self.environment}.yaml"

        if not file.exists():
            raise FileNotFoundError(file)

        with open(file, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        return self.config

    def get(self, key, default=None):

        keys = key.split(".")

        value = self.config

        for k in keys:

            if isinstance(value, dict):

                value = value.get(k)

            else:

                return default

        return value if value is not None else default

    def reload(self):

        return self.load()

    def validate(self):

        required = [
            "app",
            "logging",
            "data"
        ]

        for key in required:

            if key not in self.config:

                raise ValueError(
                    f"Missing configuration section: {key}"
                )

        return True