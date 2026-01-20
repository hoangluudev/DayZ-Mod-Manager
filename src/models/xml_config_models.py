"""
XML Configuration Models for DayZ Mission Files.

This module defines dataclasses and interfaces for all known DayZ mission XML config file types.
It provides:
- Structured parsing of XML files
- Merge rules and conflict detection
- Smart deduplication logic for merging entries

The models are designed to be flexible and support:
- Detection of file types by root element or filename
- Understanding which fields can be merged/duplicated
- Providing merge strategies for conflict resolution
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Protocol, Type, TypeVar, Union
from xml.etree import ElementTree as ET
import re


# ==============================================================================
# ENUMS AND CONSTANTS
# ==============================================================================

class MergeStrategy(Enum):
    """Strategy for handling duplicate entries during merge."""
    REPLACE = auto()      # Replace entire entry (only one with same name)
    MERGE_CHILDREN = auto()  # Merge child elements (combine items from multiple sources)
    APPEND = auto()       # Append as new entry (allow duplicates)
    SKIP = auto()         # Skip if exists


class FieldMergeRule(Enum):
    """Rule for merging specific fields within an entry."""
    UNIQUE = auto()       # Must be unique (e.g., nominal, lifetime)
    ALLOW_DUPLICATE = auto()  # Can have duplicates with different name attrs (category, tag, usage)
    MERGE_CHILDREN = auto()   # Merge child items (e.g., items in cargo)
    REPLACE = auto()      # Replace value entirely
    POSITION_APPEND = auto()  # Append positions (e.g., pos in events)


@dataclass
class FieldDefinition:
    """Definition of a field/tag within an XML entry."""
    tag: str
    is_required: bool = False
    merge_rule: FieldMergeRule = FieldMergeRule.UNIQUE
    key_attribute: Optional[str] = None  # Attribute used as unique key (e.g., "name")
    value_attribute: Optional[str] = None  # Attribute for value (e.g., "chance")
    has_children: bool = False
    child_field: Optional['FieldDefinition'] = None


# ==============================================================================
# BASE INTERFACES / PROTOCOLS
# ==============================================================================

class XMLConfigModel(Protocol):
    """Protocol for XML config models."""
    
    @classmethod
    def get_root_element(cls) -> str:
        """Return the expected root element name."""
        ...
    
    @classmethod
    def get_entry_element(cls) -> str:
        """Return the entry element name (child of root)."""
        ...
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        """Return the attribute used as unique key for entries."""
        ...
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        """Return list of field definitions for this config type."""
        ...
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        """Return the default merge strategy for this config type."""
        ...
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        """Return True if entries can have their children merged."""
        ...


# ==============================================================================
# CONFIG FILE TYPE DEFINITIONS
# ==============================================================================

@dataclass
class TypesXMLModel:
    """
    Model for types.xml - Main item spawn configuration.
    
    Structure:
    <types>
        <type name="ItemName">
            <nominal>10</nominal>
            <lifetime>14400</lifetime>
            <restock>0</restock>
            <min>5</min>
            <quantmin>-1</quantmin>
            <quantmax>-1</quantmax>
            <cost>100</cost>
            <flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0" />
            <category name="tools" />
            <tag name="shelves" />
            <usage name="Industrial" />
            <usage name="Village" />
            <value name="Tier1" />
            <value name="Tier2" />
        </type>
    </types>
    
    Merge Rules:
    - nominal, lifetime, restock, min, quantmin, quantmax, cost, flags: UNIQUE (replace)
    - category, tag, usage, value: ALLOW_DUPLICATE (can have multiple with different name attr)
    """
    ROOT_ELEMENT = "types"
    ENTRY_ELEMENT = "type"
    ENTRY_KEY_ATTR = "name"
    
    # Fields that must be unique (only one per type)
    UNIQUE_FIELDS = {"nominal", "lifetime", "restock", "min", "quantmin", "quantmax", "cost", "flags"}
    
    # Fields that can have multiple entries with different name attributes
    MULTI_NAME_FIELDS = {"category", "tag", "usage", "value"}
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            # Many mods ship partial fragments (e.g., casings) that omit fields like nominal/lifetime.
            # We still consider them mergeable as long as the entry has an identifier.
            FieldDefinition("nominal", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("lifetime", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("restock", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("min", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("quantmin", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("quantmax", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("cost", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("flags", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("category", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="name"),
            FieldDefinition("tag", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="name"),
            FieldDefinition("usage", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="name"),
            FieldDefinition("value", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="name"),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.REPLACE
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return False  # Entries are replaced, not merged
    
    @classmethod
    def is_field_mergeable(cls, field_tag: str) -> bool:
        """Check if a field allows duplicate entries with different name attributes."""
        return field_tag in cls.MULTI_NAME_FIELDS
    
    @classmethod
    def get_child_key(cls, element: ET.Element) -> Optional[str]:
        """Get unique key for a child element (for deduplication)."""
        tag = element.tag
        if tag in cls.MULTI_NAME_FIELDS:
            name = element.get("name", "")
            return f"{tag}:name:{name}" if name else None
        return tag  # For unique fields, just return tag


@dataclass
class SpawnableTypesXMLModel:
    """
    Model for cfgspawnabletypes.xml - Spawnable item attachments and cargo configuration.
    
    Structure:
    <spawnabletypes>
        <type name="ItemName">
            <hoarder />
            <damage min="0.0" max="0.5" />
            <attachments chance="0.85">
                <item name="Attachment1" chance="1.0" />
                <item name="Attachment2" chance="0.5" />
            </attachments>
            <cargo chance="0.5" preset="presetName" />
        </type>
    </spawnabletypes>
    
    Merge Rules:
    - hoarder: UNIQUE (flag)
    - damage: UNIQUE (single damage range)
    - attachments: MERGE_CHILDREN (merge items from multiple sources)
    - cargo: Can have multiple cargo definitions
    """
    ROOT_ELEMENT = "spawnabletypes"
    ENTRY_ELEMENT = "type"
    ENTRY_KEY_ATTR = "name"
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        item_field = FieldDefinition("item", merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="name")
        return [
            FieldDefinition("hoarder", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("damage", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("attachments", is_required=False, merge_rule=FieldMergeRule.MERGE_CHILDREN,
                          has_children=True, child_field=item_field),
            FieldDefinition("cargo", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="preset"),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        # Some servers/mods intentionally include multiple <type name="..."> blocks
        # with different attachments/cargo groups to represent multiple loot-table options.
        # Treat same-name entries as valid and preserve them.
        return MergeStrategy.APPEND
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True


@dataclass
class RandomPresetsXMLModel:
    """
    Model for cfgrandompresets.xml - Random cargo presets configuration.
    
    Structure:
    <randompresets>
        <cargo name="presetName" chance="0.15">
            <item name="ItemName" chance="0.1" />
            <item name="ItemName2" chance="0.2" />
        </cargo>
    </randompresets>
    
    Merge Rules:
    - cargo: Identified by name attribute
    - items: MERGE_CHILDREN (merge items from multiple sources, dedupe by name)
    """
    ROOT_ELEMENT = "randompresets"
    ENTRY_ELEMENT = "cargo"
    ENTRY_KEY_ATTR = "name"
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("item", is_required=False, merge_rule=FieldMergeRule.ALLOW_DUPLICATE, 
                          key_attribute="name", value_attribute="chance"),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True
    
    @classmethod
    def get_child_key(cls, element: ET.Element) -> Optional[str]:
        """Get unique key for child element."""
        if element.tag == "item":
            return f"item:name:{element.get('name', '')}"
        return None


@dataclass
class EventsXMLModel:
    """
    Model for events.xml - Event definitions with spawn positions.
    
    Structure:
    <events>
        <event name="EventName">
            <nominal>5</nominal>
            <min>2</min>
            <max>5</max>
            <lifetime>1800</lifetime>
            <restock>600</restock>
            <saferadius>500</saferadius>
            <distanceradius>500</distanceradius>
            <cleanupradius>200</cleanupradius>
            <flags deletable="1" init_random="0" remove_damaged="1" />
            <position>fixed</position>
            <limit>mixed</limit>
            <active>1</active>
            <children>
                <child lootmax="0" lootmin="0" max="1" min="1" type="ItemName" />
            </children>
            <pos x="1234.5" y="100.0" z="5678.9" a="90.0" />
        </event>
    </events>
    
    Merge Rules:
    - Most fields: UNIQUE (only one per event)
    - pos: POSITION_APPEND (can have multiple positions, dedupe by coordinates)
    - children: MERGE_CHILDREN (can merge child items)
    """
    ROOT_ELEMENT = "events"
    ENTRY_ELEMENT = "event"
    ENTRY_KEY_ATTR = "name"
    
    UNIQUE_FIELDS = {"nominal", "min", "max", "lifetime", "restock", "saferadius", 
                     "distanceradius", "cleanupradius", "flags", "position", "limit", "active"}
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        child_field = FieldDefinition("child", merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="type")
        return [
            FieldDefinition("nominal", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("min", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("max", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("lifetime", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("restock", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("saferadius", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("distanceradius", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("cleanupradius", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("flags", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("position", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("limit", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("active", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("children", is_required=False, merge_rule=FieldMergeRule.MERGE_CHILDREN,
                          has_children=True, child_field=child_field),
            FieldDefinition("pos", is_required=False, merge_rule=FieldMergeRule.POSITION_APPEND),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True
    
    @classmethod
    def get_position_key(cls, pos_element: ET.Element) -> str:
        """Get unique key for a position element."""
        x = pos_element.get("x", "0")
        y = pos_element.get("y", "0") 
        z = pos_element.get("z", "0")
        a = pos_element.get("a", "0")
        return f"pos:{x}:{y}:{z}:{a}"


@dataclass
class EventSpawnsXMLModel:
    """
    Model for cfgeventspawns.xml - Event spawn positions.
    
    Structure:
    <eventposdef>
        <event name="EventName">
            <zone smin="1" smax="3" dmin="3" dmax="5" r="45" />
            <pos x="1234.5" z="5678.9" a="90.0" />
            <pos x="2345.6" z="6789.0" a="180.0" />
        </event>
    </eventposdef>
    
    Merge Rules:
    - zone: UNIQUE (only one zone definition)
    - pos: POSITION_APPEND (merge positions from multiple sources)
    """
    ROOT_ELEMENT = "eventposdef"
    ENTRY_ELEMENT = "event"
    ENTRY_KEY_ATTR = "name"
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("zone", is_required=False, merge_rule=FieldMergeRule.UNIQUE),
            FieldDefinition("pos", is_required=False, merge_rule=FieldMergeRule.POSITION_APPEND),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True
    
    @classmethod
    def get_position_key(cls, pos_element: ET.Element) -> str:
        """Get unique key for a position element."""
        x = pos_element.get("x", "0")
        z = pos_element.get("z", "0")
        a = pos_element.get("a", "0")
        return f"pos:{x}:{z}:{a}"


@dataclass
class IgnoreListXMLModel:
    """
    Model for cfgignorelist.xml - Items to ignore in economy.
    
    Structure:
    <ignore>
        <type name="ItemName"></type>
        <type name="ItemName2"></type>
    </ignore>
    
    Merge Rules:
    - type: APPEND (add new entries, dedupe by name)
    """
    ROOT_ELEMENT = "ignore"
    ENTRY_ELEMENT = "type"
    ENTRY_KEY_ATTR = "name"
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return []  # type elements are self-contained
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.APPEND
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return False


@dataclass
class WeatherXMLModel:
    """
    Model for cfgweather.xml - Weather configuration.
    
    Structure:
    <weather reset="0" enable="0">
        <overcast>
            <current actual="0.45" time="120" duration="240" />
            <limits min="0.0" max="1.0" />
            <timelimits min="600" max="900" />
            <changelimits min="0.0" max="1.0" />
        </overcast>
        <fog>...</fog>
        <rain>...</rain>
        <windMagnitude>...</windMagnitude>
        <windDirection>...</windDirection>
        <snowfall>...</snowfall>
        <storm density="1.0" threshold="0.7" timeout="20"/>
    </weather>
    
    Merge Rules:
    - Each weather type (overcast, fog, rain, etc.): REPLACE (whole section)
    - This file typically should be replaced entirely, not merged
    """
    ROOT_ELEMENT = "weather"
    ENTRY_ELEMENT = None  # No repeating entries, structured sections
    ENTRY_KEY_ATTR = None
    
    WEATHER_SECTIONS = {"overcast", "fog", "rain", "windMagnitude", "windDirection", "snowfall", "storm"}
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> Optional[str]:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> Optional[str]:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("overcast", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("fog", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("rain", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("windMagnitude", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("windDirection", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("snowfall", merge_rule=FieldMergeRule.REPLACE),
            FieldDefinition("storm", merge_rule=FieldMergeRule.REPLACE),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.REPLACE  # Typically replace whole file
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return False


@dataclass
class EconomyCoreXMLModel:
    """
    Model for cfgeconomycore.xml - Economy core configuration.
    
    Structure:
    <economycore>
        <classes>
            <rootclass name="DefaultWeapon" />
            <rootclass name="Inventory_Base" />
        </classes>
        <defaults>
            <default name="dyn_radius" value="30" />
            <default name="log_ce_loop" value="false"/>
        </defaults>
    </economycore>
    
    Merge Rules:
    - rootclass: APPEND (add new classes)
    - default: REPLACE by name (update existing or add new)
    """
    ROOT_ELEMENT = "economycore"
    ENTRY_ELEMENT = None  # Has sub-sections
    ENTRY_KEY_ATTR = None
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> Optional[str]:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> Optional[str]:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("classes", merge_rule=FieldMergeRule.MERGE_CHILDREN, has_children=True,
                          child_field=FieldDefinition("rootclass", key_attribute="name")),
            FieldDefinition("defaults", merge_rule=FieldMergeRule.MERGE_CHILDREN, has_children=True,
                          child_field=FieldDefinition("default", key_attribute="name")),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True


@dataclass
class EnvironmentXMLModel:
    """
    Model for cfgenvironment.xml - Environment/territory configuration.
    
    Structure:
    <env>
        <territories>
            <file path="env/cattle_territories.xml" />
            <territory type="Herd" name="Deer" behavior="DZDeerGroupBeh">
                <file usable="red_deer_territories" />
            </territory>
        </territories>
    </env>
    
    Merge Rules:
    - file: APPEND (add new file references)
    - territory: REPLACE by name (update existing or add new)
    """
    ROOT_ELEMENT = "env"
    ENTRY_ELEMENT = "territories"
    ENTRY_KEY_ATTR = None
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> Optional[str]:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("file", merge_rule=FieldMergeRule.ALLOW_DUPLICATE, key_attribute="path"),
            FieldDefinition("territory", merge_rule=FieldMergeRule.REPLACE, key_attribute="name"),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True


@dataclass
class MapGroupXMLModel:
    """
    Model for mapgroupcluster*.xml, mapgrouppos.xml, mapgroupdirt.xml - Map group definitions.
    
    Structure:
    <map>
        <group name="ObjectName" pos="x y z" a="angle" />
        <group name="ObjectName2" pos="x y z" rpy="roll pitch yaw" a="angle" />
    </map>
    
    Merge Rules:
    - group: APPEND (add new groups, dedupe by name+pos)
    """
    ROOT_ELEMENT = "map"
    ENTRY_ELEMENT = "group"
    ENTRY_KEY_ATTR = "name"  # But position also matters for uniqueness
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> str:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> str:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return []  # group elements are self-contained with attributes
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.APPEND
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return False
    
    @classmethod
    def get_entry_unique_key(cls, element: ET.Element) -> str:
        """Get unique key for a group element (name + position)."""
        name = element.get("name", "")
        pos = element.get("pos", "")
        a = element.get("a", "0")
        return f"{name}:{pos}:{a}"


@dataclass
class MapProtoXMLModel:
    """
    Model for mapgroupproto.xml, mapclusterproto.xml - Map prototype definitions.
    
    Structure (mapgroupproto):
    <prototype>
        <defaults>
            <default name="..." value="..." />
        </defaults>
        <group name="Land_Building" lootmax="5">
            <container name="lootFloor" ... />
            <point ... />
        </group>
    </prototype>
    
    Structure (mapclusterproto):
    <prototype>
        <clusters>
            <export name="PathD_02k" shape="path/to/model.p3d" />
        </clusters>
    </prototype>
    
    Merge Rules:
    - defaults: MERGE_CHILDREN (merge default values)
    - group: REPLACE by name (building loot definitions)
    - clusters/export: APPEND (add new cluster exports)
    """
    ROOT_ELEMENT = "prototype"
    ENTRY_ELEMENT = None  # Has multiple section types
    ENTRY_KEY_ATTR = None
    
    @classmethod
    def get_root_element(cls) -> str:
        return cls.ROOT_ELEMENT
    
    @classmethod
    def get_entry_element(cls) -> Optional[str]:
        return cls.ENTRY_ELEMENT
    
    @classmethod
    def get_entry_key_attribute(cls) -> Optional[str]:
        return cls.ENTRY_KEY_ATTR
    
    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition("defaults", merge_rule=FieldMergeRule.MERGE_CHILDREN, has_children=True,
                          child_field=FieldDefinition("default", key_attribute="name")),
            FieldDefinition("group", merge_rule=FieldMergeRule.REPLACE, key_attribute="name"),
            FieldDefinition("clusters", merge_rule=FieldMergeRule.MERGE_CHILDREN, has_children=True,
                          child_field=FieldDefinition("export", key_attribute="name")),
        ]
    
    @classmethod
    def get_merge_strategy(cls) -> MergeStrategy:
        return MergeStrategy.MERGE_CHILDREN
    
    @classmethod
    def can_merge_entries(cls) -> bool:
        return True


# ==============================================================================
# CONFIG TYPE REGISTRY
# ==============================================================================

class ConfigTypeRegistry:
    """Registry for mapping file types to their models."""
    
    # Map root element -> model class
    _root_element_map: dict[str, Type] = {
        "types": TypesXMLModel,
        "spawnabletypes": SpawnableTypesXMLModel,
        "randompresets": RandomPresetsXMLModel,
        "events": EventsXMLModel,
        "eventposdef": EventSpawnsXMLModel,
        "ignore": IgnoreListXMLModel,
        "weather": WeatherXMLModel,
        "economycore": EconomyCoreXMLModel,
        "env": EnvironmentXMLModel,
        "map": MapGroupXMLModel,
        "prototype": MapProtoXMLModel,
    }
    
    # Map filename pattern -> model class (ORDER MATTERS - more specific patterns first)
    _filename_patterns: list[tuple[str, Type]] = [
        # Specific cfg* files first
        (r"cfgspawnabletypes\.xml$", SpawnableTypesXMLModel),
        (r".*spawnabletypes.*\.xml$", SpawnableTypesXMLModel),
        (r"cfgrandompresets\.xml$", RandomPresetsXMLModel),
        (r".*randompresets.*\.xml$", RandomPresetsXMLModel),
        (r"cfgeventspawns\.xml$", EventSpawnsXMLModel),
        (r".*eventspawns.*\.xml$", EventSpawnsXMLModel),
        (r"cfgignorelist\.xml$", IgnoreListXMLModel),
        (r".*ignorelist.*\.xml$", IgnoreListXMLModel),
        (r"cfgweather\.xml$", WeatherXMLModel),
        (r".*weather.*\.xml$", WeatherXMLModel),
        (r"cfgeconomycore\.xml$", EconomyCoreXMLModel),
        (r".*economycore.*\.xml$", EconomyCoreXMLModel),
        (r"cfgenvironment\.xml$", EnvironmentXMLModel),
        (r".*environment.*\.xml$", EnvironmentXMLModel),
        # Types patterns (after specific cfg* patterns)
        (r"^types\.xml$", TypesXMLModel),
        (r".*_types\.xml$", TypesXMLModel),  # e.g., bandit_types.xml
        (r".*types.*\.xml$", TypesXMLModel),  # e.g., 'Add to Types.xml', 'myTypesFragment.xml'
        # Events
        (r"events\.xml$", EventsXMLModel),
        (r".*events.*\.xml$", EventsXMLModel),
        # Map files
        (r"mapgroupcluster.*\.xml$", MapGroupXMLModel),
        (r"mapgrouppos\.xml$", MapGroupXMLModel),
        (r"mapgroupdirt\.xml$", MapGroupXMLModel),
        (r"mapgroupproto\.xml$", MapProtoXMLModel),
        (r"mapclusterproto\.xml$", MapProtoXMLModel),
    ]
    
    @classmethod
    def get_model_by_root_element(cls, root_element: str) -> Optional[Type]:
        """Get model class by root element name."""
        return cls._root_element_map.get(root_element.lower())
    
    @classmethod
    def get_model_by_filename(cls, filename: str) -> Optional[Type]:
        """Get model class by filename pattern matching."""
        filename_lower = filename.lower()
        for pattern, model_class in cls._filename_patterns:
            if re.search(pattern, filename_lower):
                return model_class
        return None
    
    @classmethod
    def get_model_for_file(cls, file_path: Union[str, Path]) -> Optional[Type]:
        """Get model class for a file, trying root element first, then filename."""
        path = Path(file_path)
        
        # Try filename pattern first for quick match
        model = cls.get_model_by_filename(path.name)
        if model:
            return model
        
        # Try parsing and checking root element
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            model = cls.get_model_by_root_element(root.tag)
            if model:
                return model
        except Exception:
            # Fall back to content-based detection for fragment/invalid-root XML.
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                model = cls.get_model_for_content(path.name, content)
                if model:
                    return model
            except Exception:
                pass
        
        return None

    @classmethod
    def get_model_for_content(cls, filename: str, content: str) -> Optional[Type]:
        """Best-effort model detection when XML root is missing/invalid.

        Uses filename patterns first, then lightweight tag heuristics.
        """
        model = cls.get_model_by_filename(filename)
        if model:
            return model

        filename_lower = (filename or "").lower()
        text = (content or "").lower()

        # Filename substring hints (common in modded fragments)
        # NOTE: order matters; 'spawnabletypes' contains 'types'.
        if "spawnabletypes" in filename_lower:
            return SpawnableTypesXMLModel
        if "randompresets" in filename_lower:
            return RandomPresetsXMLModel
        if "eventspawns" in filename_lower:
            return EventSpawnsXMLModel
        if "ignorelist" in filename_lower:
            return IgnoreListXMLModel
        if "economycore" in filename_lower:
            return EconomyCoreXMLModel
        if "weather" in filename_lower:
            return WeatherXMLModel
        if "environment" in filename_lower:
            return EnvironmentXMLModel
        if "events" in filename_lower:
            return EventsXMLModel
        if "types" in filename_lower:
            return TypesXMLModel

        # Root-tag hints
        if "<spawnabletypes" in text:
            return SpawnableTypesXMLModel
        if "<eventposdef" in text:
            return EventSpawnsXMLModel
        if "<randompresets" in text:
            return RandomPresetsXMLModel
        if "<events" in text or "<event " in text:
            return EventsXMLModel
        if "<ignore" in text:
            return IgnoreListXMLModel
        if "<weather" in text:
            return WeatherXMLModel
        if "<economycore" in text:
            return EconomyCoreXMLModel
        if "<env" in text:
            return EnvironmentXMLModel
        if "<prototype" in text:
            return MapProtoXMLModel
        if "<map" in text and "<group" in text:
            return MapGroupXMLModel

        # Fragment heuristics
        # Spawnabletypes snippets usually contain attachments/cargo blocks.
        spawnable_score = 0
        types_score = 0

        # Spawnabletypes-only-ish tags
        for tag in ("<attachments", "<cargo", "<damage", "<hoarder", "<inventory", "<tag" ):
            if tag in text:
                # <tag> exists in types.xml too; keep it low weight.
                spawnable_score += 1 if tag != "<tag" else 0

        # Types-only-ish tags (do NOT require <nominal>)
        for tag in ("<restock", "<quantmin", "<quantmax", "<min>", "<lifetime", "<cost", "<flags", "<category", "<usage", "<value"):
            if tag in text:
                types_score += 1

        if "<type" in text and "name=" in text:
            # Shared signal
            types_score += 1
            spawnable_score += 1

        if spawnable_score > types_score and spawnable_score >= 2:
            return SpawnableTypesXMLModel
        if types_score >= 1:
            return TypesXMLModel

        return None
    
    @classmethod
    def detect_config_type(cls, file_path: Union[str, Path]) -> Optional[str]:
        """Detect config type string for a file."""
        model = cls.get_model_for_file(file_path)
        if model:
            return model.get_root_element()
        return None


# ==============================================================================
# MERGE UTILITIES
# ==============================================================================

class XMLMergeHelper:
    """Helper class for merging XML configurations."""

    @staticmethod
    def _unwrap_xml_comments_containing_tags(xml_text: str, tags: list[str]) -> tuple[str, bool]:
        """Unwrap XML comments (<!-- ... -->) that contain specific tags.

        Some mods ship valid XML entries inside XML comments. We only unwrap comment blocks
        when they clearly contain mergeable XML tags to avoid changing normal documentation.
        """
        if not xml_text or not tags:
            return xml_text, False

        safe_tags = [t for t in tags if t]
        if not safe_tags:
            return xml_text, False

        changed = False
        comment_re = re.compile(r"<!--(.*?)-->", flags=re.DOTALL)

        def _repl(m: re.Match) -> str:
            nonlocal changed
            inner = m.group(1) or ""
            inner_lower = inner.lower()
            for tag in safe_tags:
                if re.search(rf"<\s*{re.escape(tag.lower())}\b", inner_lower, flags=re.IGNORECASE):
                    changed = True
                    return inner
            return m.group(0)

        return comment_re.sub(_repl, xml_text), changed

    @staticmethod
    def analyze_xml_text(
        xml_text: str,
        model_class: Optional[Type] = None,
        filename: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return lightweight heuristics about whether a file is 'hard to scan/detect'."""
        raw = xml_text or ""
        model = model_class
        if model is None and filename:
            model = ConfigTypeRegistry.get_model_for_content(filename, raw)

        entry_tag = None
        root_tag = None
        try:
            if model is not None:
                entry_tag = getattr(model, "get_entry_element", lambda: None)()
                root_tag = getattr(model, "get_root_element", lambda: None)()
        except Exception:
            entry_tag = None
            root_tag = None

        # Non-XML preamble/postamble (common: instructions before/after XML)
        stripped = raw.lstrip("\ufeff")
        first_lt = stripped.find("<")
        last_gt = stripped.rfind(">")
        has_preamble = bool(first_lt > 0 and stripped[:first_lt].strip())
        has_postamble = bool(last_gt != -1 and last_gt + 1 < len(stripped) and stripped[last_gt + 1 :].strip())

        # Tags inside XML comments
        has_xml_comment = "<!--" in raw and "-->" in raw
        tags_to_check = [t for t in [entry_tag, root_tag] if t]
        has_tag_in_comment = False
        if has_xml_comment and tags_to_check:
            for m in re.finditer(r"<!--(.*?)-->", raw, flags=re.DOTALL):
                inner = (m.group(1) or "").lower()
                if any(re.search(rf"<\s*{re.escape(t.lower())}\b", inner, flags=re.IGNORECASE) for t in tags_to_check):
                    has_tag_in_comment = True
                    break

        return {
            "has_preamble": has_preamble,
            "has_postamble": has_postamble,
            "has_c_style_comments": bool(re.search(r"/\*.*?\*/", raw, flags=re.DOTALL)),
            "has_slashslash_comments": bool(re.search(r"^\s*//.*$", raw, flags=re.MULTILINE)),
            "has_xml_comment": has_xml_comment,
            "has_tag_in_comment": has_tag_in_comment,
            "entry_tag": entry_tag,
            "root_tag": root_tag,
        }
    
    @staticmethod
    def get_element_signature(element: ET.Element, model_class: Optional[Type] = None) -> str:
        """
        Generate a unique signature for an element based on its content.
        Used for deduplication during merge.
        """
        tag = element.tag
        
        # For map group elements (name + position) - check before name attr
        if tag.lower() == "group":
            name = element.get("name", "")
            pos = element.get("pos", "")
            return f"group:{name}:{pos}"
        
        # For position elements
        if tag.lower() == "pos":
            x = element.get("x", "")
            y = element.get("y", "")
            z = element.get("z", "")
            a = element.get("a", "")
            return f"pos:{x}:{y}:{z}:{a}"
        
        # Check for name attribute (most common)
        name = element.get("name")
        if name:
            return f"{tag}:name:{name}"
        
        # For elements with type attribute
        type_attr = element.get("type")
        if type_attr:
            return f"{tag}:type:{type_attr}"
        
        # Fallback: use all attributes
        attrs = ";".join([f"{k}={v}" for k, v in sorted(element.attrib.items())])
        return f"{tag}:{attrs}"
    
    @staticmethod
    def can_merge_elements(elem1: ET.Element, elem2: ET.Element, model_class: Optional[Type] = None) -> bool:
        """Check if two elements can be merged (same signature)."""
        sig1 = XMLMergeHelper.get_element_signature(elem1, model_class)
        sig2 = XMLMergeHelper.get_element_signature(elem2, model_class)
        return sig1 == sig2

    @staticmethod
    def sanitize_xml_text(xml_text: str) -> str:
        """Make common 'modder XML fragments' parseable.

        Handles:
        - UTF-8 BOM
        - C-style /* ... */ blocks (not valid XML)
        - // line comments (not valid XML)
        """
        if not xml_text:
            return ""

        text = xml_text
        # Remove BOM
        text = text.lstrip("\ufeff")

        # Strip C-style block comments
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        # Strip C++-style line comments
        text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)

        # Many mods use non-XML "banner" lines like:
        # <!------------------SOMETHING------------------>
        # These are NOT valid XML comments (XML comments must start with <!--), and will break parsing.
        text = re.sub(r"^\s*<!-+.*?-+>\s*$", "", text, flags=re.MULTILINE)

        # Some modders include plain text instructions before/after XML.
        # Best-effort trim to the first '<' and last '>' so wrapping can work.
        first_lt = text.find("<")
        last_gt = text.rfind(">")
        if first_lt != -1 and last_gt != -1 and last_gt > first_lt:
            text = text[first_lt:last_gt + 1]

        return text

    @staticmethod
    def parse_xml_text(
        xml_text: str,
        model_class: Optional[Type] = None,
        filename: Optional[str] = None,
    ) -> ET.Element:
        """Parse XML text, supporting fragments without a parent/root element."""
        root, _meta = XMLMergeHelper.parse_xml_text_with_meta(
            xml_text, model_class=model_class, filename=filename
        )
        return root

    @staticmethod
    def parse_xml_text_with_meta(
        xml_text: str,
        model_class: Optional[Type] = None,
        filename: Optional[str] = None,
    ) -> tuple[ET.Element, dict[str, Any]]:
        """Parse XML text with best-effort recovery and return metadata about recovery."""
        meta: dict[str, Any] = {
            "unwrap_comments": False,
            "used_wrap_root": False,
            "used_extract_entries": False,
        }

        text = XMLMergeHelper.sanitize_xml_text(xml_text)
        model = model_class
        if model is None and filename:
            model = ConfigTypeRegistry.get_model_for_content(filename, text)

        entry_tag = None
        root_tag = None
        if model is not None:
            try:
                entry_tag = model.get_entry_element()
            except Exception:
                entry_tag = None
            try:
                root_tag = model.get_root_element()
            except Exception:
                root_tag = None

        # Unwrap comment blocks that contain relevant tags (e.g., <type> entries)
        tags_to_unwrap = [t for t in [entry_tag, root_tag] if t]
        text, did_unwrap = XMLMergeHelper._unwrap_xml_comments_containing_tags(text, tags_to_unwrap)
        meta["unwrap_comments"] = did_unwrap

        # Remove XML declaration if we might wrap.
        text_no_decl = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", text, flags=re.IGNORECASE)

        # 1) Try as-is
        try:
            root = ET.fromstring(text_no_decl)
        except Exception:
            root = None

        if root is not None:
            # If this parsed as a single entry element (e.g., <type>...</type>), normalize to a
            # synthetic root when we know the model.
            if model is not None and entry_tag and root_tag:
                try:
                    if root.tag.lower() == entry_tag.lower() and root_tag.lower() != entry_tag.lower():
                        synthetic = ET.Element(root_tag)
                        synthetic.append(root)
                        return synthetic, meta
                except Exception:
                    pass
            return root, meta

        # 2) Wrap into model root (fragment with multiple top-level entries)
        root_tag = (root_tag if root_tag else "root")
        wrapped = f"<{root_tag}>\n{text_no_decl}\n</{root_tag}>"
        try:
            meta["used_wrap_root"] = True
            return ET.fromstring(wrapped), meta
        except Exception:
            meta["used_wrap_root"] = False

        # 3) Last-resort recovery: extract individual entry elements.
        if entry_tag and root_tag and model is not None:
            extracted = XMLMergeHelper._extract_entry_elements(text_no_decl, entry_tag)
            if extracted:
                meta["used_extract_entries"] = True
                synthetic = ET.Element(root_tag)
                for elem in extracted:
                    synthetic.append(elem)
                return synthetic, meta

        # Nothing worked
        return ET.fromstring(wrapped), meta

    @staticmethod
    def _extract_entry_elements(xml_text: str, entry_tag: str) -> list[ET.Element]:
        """Extract and parse individual entry elements from malformed XML."""
        if not xml_text or not entry_tag:
            return []

        tag = re.escape(entry_tag)
        pattern = re.compile(
            rf"(<{tag}\b[^>]*?/\s*>|<{tag}\b[^>]*>.*?</{tag}\s*>)",
            flags=re.IGNORECASE | re.DOTALL,
        )

        elements: list[ET.Element] = []
        for m in pattern.finditer(xml_text):
            snippet = (m.group(1) or "").strip()
            if not snippet:
                continue
            try:
                elements.append(ET.fromstring(snippet))
            except Exception:
                continue

        return elements

    @staticmethod
    def parse_xml_file(
        file_path: Union[str, Path],
        model_hint: Optional[Type] = None,
    ) -> tuple[ET.ElementTree, ET.Element, Optional[Type]]:
        """Parse an XML file with best-effort support for fragments.

        Returns (tree, root, detected_model).
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        model = model_hint or ConfigTypeRegistry.get_model_for_file(path) or ConfigTypeRegistry.get_model_for_content(path.name, content)
        root = XMLMergeHelper.parse_xml_text(content, model_class=model, filename=path.name)
        tree = ET.ElementTree(root)
        return tree, root, model

    @staticmethod
    def parse_xml_file_with_meta(
        file_path: Union[str, Path],
        model_hint: Optional[Type] = None,
    ) -> tuple[ET.ElementTree, ET.Element, Optional[Type], dict[str, Any]]:
        """Parse an XML file with best-effort support for fragments and return metadata."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        model = model_hint or ConfigTypeRegistry.get_model_for_file(path) or ConfigTypeRegistry.get_model_for_content(path.name, content)
        root, meta = XMLMergeHelper.parse_xml_text_with_meta(content, model_class=model, filename=path.name)
        meta.update(XMLMergeHelper.analyze_xml_text(content, model_class=model, filename=path.name))
        tree = ET.ElementTree(root)
        return tree, root, model, meta
    
    @staticmethod
    def merge_children(parent1: ET.Element, parent2: ET.Element, 
                      model_class: Optional[Type] = None) -> list[ET.Element]:
        """
        Merge children from two parent elements, avoiding duplicates.
        Returns list of merged children.
        """
        merged = []
        seen_signatures = set()
        
        # Add all children from first parent
        for child in parent1:
            sig = XMLMergeHelper.get_element_signature(child, model_class)
            if sig not in seen_signatures:
                merged.append(child)
                seen_signatures.add(sig)
        
        # Add non-duplicate children from second parent
        for child in parent2:
            sig = XMLMergeHelper.get_element_signature(child, model_class)
            if sig not in seen_signatures:
                # Clone the element
                cloned = ET.Element(child.tag, child.attrib)
                cloned.text = child.text
                cloned.tail = child.tail
                for subchild in child:
                    cloned.append(subchild)
                merged.append(cloned)
                seen_signatures.add(sig)
        
        return merged
    
    @staticmethod
    def get_mergeable_fields(model_class: Type) -> list[str]:
        """Get list of field tags that allow merging/duplicates."""
        if not hasattr(model_class, 'get_field_definitions'):
            return []
        
        mergeable = []
        for field_def in model_class.get_field_definitions():
            if field_def.merge_rule in [FieldMergeRule.ALLOW_DUPLICATE, 
                                         FieldMergeRule.MERGE_CHILDREN,
                                         FieldMergeRule.POSITION_APPEND]:
                mergeable.append(field_def.tag)
        return mergeable
    
    @staticmethod
    def get_unique_fields(model_class: Type) -> list[str]:
        """Get list of field tags that must be unique."""
        if not hasattr(model_class, 'get_field_definitions'):
            return []
        
        unique = []
        for field_def in model_class.get_field_definitions():
            if field_def.merge_rule in [FieldMergeRule.UNIQUE, FieldMergeRule.REPLACE]:
                unique.append(field_def.tag)
        return unique


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    'MergeStrategy',
    'FieldMergeRule',
    
    # Base classes
    'FieldDefinition',
    'XMLConfigModel',
    
    # Model classes
    'TypesXMLModel',
    'SpawnableTypesXMLModel',
    'RandomPresetsXMLModel',
    'EventsXMLModel',
    'EventSpawnsXMLModel',
    'IgnoreListXMLModel',
    'WeatherXMLModel',
    'EconomyCoreXMLModel',
    'EnvironmentXMLModel',
    'MapGroupXMLModel',
    'MapProtoXMLModel',
    
    # Registry and helpers
    'ConfigTypeRegistry',
    'XMLMergeHelper',
]
