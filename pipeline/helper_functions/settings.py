import ast
import os
import toml
from pathlib import Path

from dotenv import dotenv_values


def load_config():
    env_config = env_load(os.path.join(os.path.dirname(__file__), '..', '.env'))

    with open('pipeline/config.toml', 'r') as f:
        config = toml.load(f)

        if config['produce_headline_totals']:
            config['variables'].append('headline_totals')

    return {**env_config, **config}


def env_load(env_path):
    if not Path(env_path).exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    return dict(dotenv_values(env_path))


CONFIG = load_config()
