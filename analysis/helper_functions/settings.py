import ast
import os
import toml
import shutil
from pathlib import Path

from dotenv import dotenv_values


def return_path(file):
    return Path(__file__).parent.parent/file


def load_config():
    default_config = return_path("config.toml")
    local_config = return_path("config.local.toml")

    if not default_config.exists():
        raise FileNotFoundError(f"config.toml file not found: {default_config}")

    # Create local config from default if it doesn't exist
    if not local_config.exists():
        print("\nCreating config.local.toml file")
        shutil.copy(default_config, local_config)

    # Always use local config
    with open(local_config, 'r') as f:
        print("\nLoading config.local.toml")
        config = toml.load(f)

    if config['produce_headline_totals']:
        config['variables'].append('headline_totals')

    return config


def load_settings():
    env_config = load_env()
    config = load_config()

    return {**env_config, **config}


def load_env():
    env_path = return_path('.env')

    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    return dict(dotenv_values(env_path))


CONFIG = load_settings()
