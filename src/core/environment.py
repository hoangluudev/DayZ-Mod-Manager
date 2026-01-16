"""
Environment Configuration
Handles environment-specific settings (dev, prod).
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Environment(str, Enum):
    """Application environment modes."""
    DEVELOPMENT = "dev"
    PRODUCTION = "prod"
    TEST = "test"


@dataclass(frozen=True)
class EnvironmentConfig:
    """Environment-specific configuration."""
    
    # Debug settings
    debug: bool = False
    verbose_logging: bool = False
    
    # Feature flags
    enable_hot_reload: bool = False
    enable_dev_tools: bool = False
    
    # Paths (can be overridden per environment)
    log_level: str = "INFO"


# Environment configurations
_CONFIGS = {
    Environment.DEVELOPMENT: EnvironmentConfig(
        debug=True,
        verbose_logging=True,
        enable_hot_reload=True,
        enable_dev_tools=True,
        log_level="DEBUG",
    ),
    Environment.PRODUCTION: EnvironmentConfig(
        debug=False,
        verbose_logging=False,
        enable_hot_reload=False,
        enable_dev_tools=False,
        log_level="WARNING",
    ),
    Environment.TEST: EnvironmentConfig(
        debug=True,
        verbose_logging=True,
        enable_hot_reload=False,
        enable_dev_tools=False,
        log_level="DEBUG",
    ),
}


def get_environment() -> Environment:
    """
    Get the current environment from DAYZMM_ENV variable.
    
    Returns:
        Environment enum value, defaults to PRODUCTION
    """
    env_str = os.environ.get("DAYZMM_ENV", "prod").lower()
    try:
        return Environment(env_str)
    except ValueError:
        return Environment.PRODUCTION


def get_config() -> EnvironmentConfig:
    """
    Get the configuration for the current environment.
    
    Returns:
        EnvironmentConfig for current environment
    """
    return _CONFIGS.get(get_environment(), _CONFIGS[Environment.PRODUCTION])


def is_development() -> bool:
    """Check if running in development mode."""
    return get_environment() == Environment.DEVELOPMENT


def is_production() -> bool:
    """Check if running in production mode."""
    return get_environment() == Environment.PRODUCTION


# Singleton-like access
ENV = get_environment()
CONFIG = get_config()
