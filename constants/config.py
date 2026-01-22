"""
Configuration constants for unified config tab.
"""

from dataclasses import dataclass, field
from typing import Optional


# Priority keywords for mod sorting
# Lower index = higher priority in load order
MOD_PRIORITY_KEYWORDS = [
    ["cf", "communityframework", "community-framework", "community_framework"],
    ["community-online-tools", "cot", "communityonlinetools"],
    ["dabs", "dabs framework", "dabsframework"],
    ["vppadmintools", "vpp", "vppadmin"],
    ["expansion", "dayzexpansion", "expansioncore"],
    ["expansionmod"],
    ["gamelab", "gamelabs"],
    ["soundlib", "sound library"],
    ["buildersitems", "builderstitems"],
    ["airdrop"],
]


@dataclass
class ConfigFieldDef:
    """Definition for a server config field."""

    type: str  # "text", "int", "bool"
    default: any
    tooltip_key: str = ""
    min_val: Optional[int] = None
    max_val: Optional[int] = None


# Server config field definitions
CONFIG_FIELDS: dict[str, ConfigFieldDef] = {
    # Server Info
    "hostname": ConfigFieldDef("text", "DayZ Server", "config.tooltip.hostname"),
    "password": ConfigFieldDef("text", "", "config.tooltip.password"),
    "passwordAdmin": ConfigFieldDef("text", "", "config.tooltip.password_admin"),
    "maxPlayers": ConfigFieldDef("int", 60, "config.tooltip.max_players", 1, 127),
    "instanceId": ConfigFieldDef("int", 1, "config.tooltip.instance_id", 1, 999),
    # Security
    "verifySignatures": ConfigFieldDef(
        "int", 2, "config.tooltip.verify_signatures", 0, 2
    ),
    "forceSameBuild": ConfigFieldDef("bool", True, "config.tooltip.force_same_build"),
    "enableWhitelist": ConfigFieldDef("bool", False, "config.tooltip.whitelist"),
    # Gameplay
    "disableVoN": ConfigFieldDef("bool", False, "config.tooltip.disable_von"),
    "vonCodecQuality": ConfigFieldDef("int", 20, "config.tooltip.von_quality", 0, 30),
    "disable3rdPerson": ConfigFieldDef("bool", False, "config.tooltip.disable_3p"),
    "disableCrosshair": ConfigFieldDef(
        "bool", False, "config.tooltip.disable_crosshair"
    ),
    "disableRespawnDialog": ConfigFieldDef(
        "bool", False, "config.tooltip.respawn_dialog"
    ),
    "respawnTime": ConfigFieldDef("int", 5, "config.tooltip.respawn_time", 0, 1800),
    # Time
    "serverTime": ConfigFieldDef("text", "SystemTime", "config.tooltip.server_time"),
    "serverTimeAcceleration": ConfigFieldDef(
        "int", 1, "config.tooltip.time_accel", 0, 64
    ),
    "serverNightTimeAcceleration": ConfigFieldDef(
        "int", 1, "config.tooltip.night_accel", 0, 64
    ),
    "serverTimePersistent": ConfigFieldDef(
        "bool", False, "config.tooltip.time_persistent"
    ),
    # Performance
    "guaranteedUpdates": ConfigFieldDef(
        "bool", True, "config.tooltip.guaranteed_updates"
    ),
    "steamProtocolMaxDataSize": ConfigFieldDef(
        "int", 8192, "config.tooltip.steam_protocol_max_data_size", 0, 65536
    ),
    "loginQueueConcurrentPlayers": ConfigFieldDef(
        "int", 5, "config.tooltip.login_queue", 1, 25
    ),
    "loginQueueMaxPlayers": ConfigFieldDef(
        "int", 500, "config.tooltip.login_queue_max", 1, 500
    ),
    # Storage
    "storeHouseStateDisabled": ConfigFieldDef(
        "bool", False, "config.tooltip.store_house"
    ),
    "storageAutoFix": ConfigFieldDef("bool", True, "config.tooltip.storage_fix"),
    "disableBaseDamage": ConfigFieldDef("bool", False, "config.tooltip.base_damage"),
    "disableContainerDamage": ConfigFieldDef(
        "bool", False, "config.tooltip.container_damage"
    ),
}


@dataclass
class MapOption:
    """Available map/mission template option."""

    template: str
    display_name: str


AVAILABLE_MAPS = [
    MapOption("dayzOffline.chernarusplus", "Chernarus (Vanilla)"),
    MapOption("dayzOffline.enoch", "Livonia (DLC)"),
    MapOption("dayzOffline.sakhal", "Sakhal (DLC)"),
]


# Launcher default values
@dataclass
class LauncherDefaults:
    """Default values for launcher configuration."""

    server_name: str = "DayZ_Server"
    config_file: str = "serverDZ.cfg"
    port: int = 2302
    cpu_count: int = 4
    timeout: int = 86440
    do_logs: bool = True
    admin_log: bool = True
    net_log: bool = True
    freeze_check: bool = True
    use_mods_file: bool = True


LAUNCHER_DEFAULTS = LauncherDefaults()


def get_mod_priority(mod_name: str) -> int:
    """
    Get priority score for a mod (lower = higher priority).

    Args:
        mod_name: Name of the mod (with or without @ prefix)

    Returns:
        Priority index, lower means it should load first
    """
    name_lower = (
        mod_name.lower()
        .replace("@", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )
    for priority, keywords in enumerate(MOD_PRIORITY_KEYWORDS):
        for keyword in keywords:
            keyword_clean = keyword.replace(" ", "").replace("-", "").replace("_", "")
            if keyword_clean in name_lower or name_lower in keyword_clean:
                return priority
    return len(MOD_PRIORITY_KEYWORDS) + 1
