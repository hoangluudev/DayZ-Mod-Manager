"""
Vehicle Configuration Models for DayZ Mission Files.

This module defines dataclasses for vehicle management across multiple config files:
- events.xml: Vehicle spawn events with variants
- types.xml: Wheel/part spawn configuration  
- cfgspawnabletypes.xml: Vehicle attachments/parts
- cfgeventspawns.xml: Vehicle spawn positions

Supports both vanilla and modded vehicles with import/export functionality.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Union
from xml.etree import ElementTree as ET
import json
import uuid


# ==============================================================================
# ENUMS
# ==============================================================================

class VehicleCategory(Enum):
    """Category of vehicle (vanilla or modded)."""
    VANILLA = "vanilla"
    MODDED = "modded"


class PartLabel(Enum):
    """Labels for vehicle parts to improve UX."""
    WHEEL = "wheel"
    SPARE_WHEEL = "spare_wheel"
    SPARK_PLUG = "spark_plug"
    GLOW_PLUG = "glow_plug"
    BATTERY = "battery"
    RADIATOR = "radiator"
    HEADLIGHT = "headlight"
    DOOR = "door"
    HOOD = "hood"
    TRUNK = "trunk"
    FUEL_TANK = "fuel_tank"
    ENGINE = "engine"
    OTHER = "other"


# ==============================================================================
# VEHICLE PART MODEL
# ==============================================================================

@dataclass
class VehiclePart:
    """
    Represents a vehicle part/attachment.
    
    Used in cfgspawnabletypes.xml:
    <attachments chance="1.00">
        <item name="Hatchback_02_Wheel" chance="0.80" />
    </attachments>
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    classname: str = ""  # e.g., "Hatchback_02_Wheel", "SparkPlug"
    chance: float = 1.0  # Spawn chance (0.0 to 1.0)
    attachment_chance: float = 1.0  # Parent attachment chance
    label: PartLabel = PartLabel.OTHER  # UI label for part type
    description: str = ""  # UI description (not used in XML)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "classname": self.classname,
            "chance": self.chance,
            "attachment_chance": self.attachment_chance,
            "label": self.label.value,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VehiclePart":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            classname=data.get("classname", ""),
            chance=data.get("chance", 1.0),
            attachment_chance=data.get("attachment_chance", 1.0),
            label=PartLabel(data.get("label", "other")),
            description=data.get("description", ""),
        )
    
    def to_xml_element(self) -> ET.Element:
        """Generate XML element for cfgspawnabletypes.xml."""
        attachments = ET.Element("attachments")
        attachments.set("chance", f"{self.attachment_chance:.2f}")
        
        item = ET.SubElement(attachments, "item")
        item.set("name", self.classname)
        item.set("chance", f"{self.chance:.2f}")
        
        return attachments


# ==============================================================================
# VEHICLE VARIANT MODEL
# ==============================================================================

@dataclass
class VehicleVariant:
    """
    Represents a vehicle variant (color/style variation).
    
    Used in events.xml children:
    <child lootmax="0" lootmin="0" max="5" min="3" type="Hatchback_02_Black"/>
    
    And in cfgspawnabletypes.xml:
    <type name="Hatchback_02_Black">...</type>
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    classname: str = ""  # e.g., "Hatchback_02_Black"
    description: str = ""  # UI description (not used in XML)
    
    # Events.xml child settings
    min_spawn: int = 3  # min attribute
    max_spawn: int = 5  # max attribute
    loot_min: int = 0  # lootmin attribute
    loot_max: int = 0  # lootmax attribute
    
    # Parts/attachments for this variant
    parts: list[VehiclePart] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "classname": self.classname,
            "description": self.description,
            "min_spawn": self.min_spawn,
            "max_spawn": self.max_spawn,
            "loot_min": self.loot_min,
            "loot_max": self.loot_max,
            "parts": [p.to_dict() for p in self.parts],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VehicleVariant":
        """Create from dictionary."""
        variant = cls(
            id=data.get("id", str(uuid.uuid4())),
            classname=data.get("classname", ""),
            description=data.get("description", ""),
            min_spawn=data.get("min_spawn", 3),
            max_spawn=data.get("max_spawn", 5),
            loot_min=data.get("loot_min", 0),
            loot_max=data.get("loot_max", 0),
        )
        variant.parts = [VehiclePart.from_dict(p) for p in data.get("parts", [])]
        return variant
    
    def to_event_child_element(self) -> ET.Element:
        """Generate XML element for events.xml children."""
        child = ET.Element("child")
        child.set("lootmax", str(self.loot_max))
        child.set("lootmin", str(self.loot_min))
        child.set("max", str(self.max_spawn))
        child.set("min", str(self.min_spawn))
        child.set("type", self.classname)
        return child
    
    def to_spawnable_type_element(self) -> ET.Element:
        """Generate XML element for cfgspawnabletypes.xml."""
        type_elem = ET.Element("type")
        type_elem.set("name", self.classname)
        
        for part in self.parts:
            type_elem.append(part.to_xml_element())
        
        return type_elem
    
    def clone(self) -> "VehicleVariant":
        """Create a deep copy of this variant."""
        return VehicleVariant.from_dict(self.to_dict())


# ==============================================================================
# SPAWN POSITION MODEL
# ==============================================================================

@dataclass
class SpawnPosition:
    """
    Represents a vehicle spawn position.
    
    Used in cfgeventspawns.xml:
    <pos x="3405.335205" z="12239.047851" a="189.571152" />
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    x: float = 0.0
    y: Optional[float] = None  # Optional height
    z: float = 0.0
    a: float = 0.0  # Angle/rotation
    
    # Track if this position is borrowed from vanilla
    borrowed_from: Optional[str] = None  # Vehicle model classname if borrowed
    is_custom: bool = True  # False if borrowed from vanilla
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        data = {
            "id": self.id,
            "x": self.x,
            "z": self.z,
            "a": self.a,
            "borrowed_from": self.borrowed_from,
            "is_custom": self.is_custom,
        }
        if self.y is not None:
            data["y"] = self.y
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "SpawnPosition":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=data.get("x", 0.0),
            y=data.get("y"),
            z=data.get("z", 0.0),
            a=data.get("a", 0.0),
            borrowed_from=data.get("borrowed_from"),
            is_custom=data.get("is_custom", True),
        )
    
    def to_xml_element(self) -> ET.Element:
        """Generate XML element for cfgeventspawns.xml."""
        pos = ET.Element("pos")
        pos.set("x", str(self.x))
        pos.set("z", str(self.z))
        pos.set("a", str(self.a))
        if self.y is not None:
            pos.set("y", str(self.y))
        return pos
    
    @classmethod
    def from_xml_element(cls, elem: ET.Element) -> "SpawnPosition":
        """Create from XML element."""
        return cls(
            x=float(elem.get("x", 0)),
            y=float(elem.get("y")) if elem.get("y") else None,
            z=float(elem.get("z", 0)),
            a=float(elem.get("a", 0)),
            is_custom=True,
        )
    
    def get_key(self) -> str:
        """Get unique key for deduplication."""
        y_part = "" if self.y is None else f":{self.y:.2f}"
        return f"{self.x:.2f}{y_part}:{self.z:.2f}:{self.a:.2f}"


# ==============================================================================
# WHEEL/PART TYPE CONFIG MODEL
# ==============================================================================

@dataclass
class WheelTypeConfig:
    """
    Represents wheel/part spawn configuration in types.xml.
    
    Example:
    <type name="Hatchback_02_Wheel">
        <nominal>40</nominal>
        <lifetime>28800</lifetime>
        <restock>0</restock>
        <min>30</min>
        <quantmin>-1</quantmin>
        <quantmax>-1</quantmax>
        <cost>100</cost>
        <flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0" />
        <category name="lootdispatch" />
        <tag name="floor" />
        <usage name="Industrial" />
    </type>
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    classname: str = ""  # e.g., "Hatchback_02_Wheel"
    description: str = ""  # UI description
    
    # Spawn settings
    nominal: int = 40
    min: int = 30
    lifetime: int = 28800
    restock: int = 0
    quantmin: int = -1
    quantmax: int = -1
    cost: int = 100
    
    # Flags
    count_in_cargo: int = 0
    count_in_hoarder: int = 0
    count_in_map: int = 1
    count_in_player: int = 0
    crafted: int = 0
    deloot: int = 0
    
    # Categories and tags (map-specific)
    category: str = "lootdispatch"
    tags: list[str] = field(default_factory=lambda: ["floor"])
    usages: list[str] = field(default_factory=lambda: ["Industrial"])
    values: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "classname": self.classname,
            "description": self.description,
            "nominal": self.nominal,
            "min": self.min,
            "lifetime": self.lifetime,
            "restock": self.restock,
            "quantmin": self.quantmin,
            "quantmax": self.quantmax,
            "cost": self.cost,
            "count_in_cargo": self.count_in_cargo,
            "count_in_hoarder": self.count_in_hoarder,
            "count_in_map": self.count_in_map,
            "count_in_player": self.count_in_player,
            "crafted": self.crafted,
            "deloot": self.deloot,
            "category": self.category,
            "tags": self.tags,
            "usages": self.usages,
            "values": self.values,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WheelTypeConfig":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            classname=data.get("classname", ""),
            description=data.get("description", ""),
            nominal=data.get("nominal", 40),
            min=data.get("min", 30),
            lifetime=data.get("lifetime", 28800),
            restock=data.get("restock", 0),
            quantmin=data.get("quantmin", -1),
            quantmax=data.get("quantmax", -1),
            cost=data.get("cost", 100),
            count_in_cargo=data.get("count_in_cargo", 0),
            count_in_hoarder=data.get("count_in_hoarder", 0),
            count_in_map=data.get("count_in_map", 1),
            count_in_player=data.get("count_in_player", 0),
            crafted=data.get("crafted", 0),
            deloot=data.get("deloot", 0),
            category=data.get("category", "lootdispatch"),
            tags=data.get("tags", ["floor"]),
            usages=data.get("usages", ["Industrial"]),
            values=data.get("values", []),
        )
    
    def to_xml_element(self) -> ET.Element:
        """Generate XML element for types.xml."""
        type_elem = ET.Element("type")
        type_elem.set("name", self.classname)
        
        # Add child elements
        ET.SubElement(type_elem, "nominal").text = str(self.nominal)
        ET.SubElement(type_elem, "lifetime").text = str(self.lifetime)
        ET.SubElement(type_elem, "restock").text = str(self.restock)
        ET.SubElement(type_elem, "min").text = str(self.min)
        ET.SubElement(type_elem, "quantmin").text = str(self.quantmin)
        ET.SubElement(type_elem, "quantmax").text = str(self.quantmax)
        ET.SubElement(type_elem, "cost").text = str(self.cost)
        
        # Flags
        flags = ET.SubElement(type_elem, "flags")
        flags.set("count_in_cargo", str(self.count_in_cargo))
        flags.set("count_in_hoarder", str(self.count_in_hoarder))
        flags.set("count_in_map", str(self.count_in_map))
        flags.set("count_in_player", str(self.count_in_player))
        flags.set("crafted", str(self.crafted))
        flags.set("deloot", str(self.deloot))
        
        # Category
        if self.category:
            cat = ET.SubElement(type_elem, "category")
            cat.set("name", self.category)
        
        # Tags
        for tag in self.tags:
            tag_elem = ET.SubElement(type_elem, "tag")
            tag_elem.set("name", tag)
        
        # Usages
        for usage in self.usages:
            usage_elem = ET.SubElement(type_elem, "usage")
            usage_elem.set("name", usage)
        
        # Values
        for value in self.values:
            value_elem = ET.SubElement(type_elem, "value")
            value_elem.set("name", value)
        
        return type_elem


# ==============================================================================
# EVENT CONFIG MODEL (for events.xml settings)
# ==============================================================================

@dataclass
class EventConfig:
    """
    Event configuration settings from events.xml.
    
    Example:
    <event name="VehicleHatchback02">
        <nominal>8</nominal>
        <min>5</min>
        <max>11</max>
        <lifetime>300</lifetime>
        <restock>0</restock>
        <saferadius>500</saferadius>
        <distanceradius>500</distanceradius>
        <cleanupradius>200</cleanupradius>
        <flags deletable="0" init_random="0" remove_damaged="1"/>
        <position>fixed</position>
        <limit>mixed</limit>
        <active>1</active>
    </event>
    """
    nominal: int = 8
    min: int = 5
    max: int = 11
    lifetime: int = 300
    restock: int = 0
    saferadius: int = 500
    distanceradius: int = 500
    cleanupradius: int = 200
    
    # Flags
    deletable: int = 0
    init_random: int = 0
    remove_damaged: int = 1
    
    # Other settings
    position: str = "fixed"
    limit: str = "mixed"
    active: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "nominal": self.nominal,
            "min": self.min,
            "max": self.max,
            "lifetime": self.lifetime,
            "restock": self.restock,
            "saferadius": self.saferadius,
            "distanceradius": self.distanceradius,
            "cleanupradius": self.cleanupradius,
            "deletable": self.deletable,
            "init_random": self.init_random,
            "remove_damaged": self.remove_damaged,
            "position": self.position,
            "limit": self.limit,
            "active": self.active,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EventConfig":
        """Create from dictionary."""
        return cls(
            nominal=data.get("nominal", 8),
            min=data.get("min", 5),
            max=data.get("max", 11),
            lifetime=data.get("lifetime", 300),
            restock=data.get("restock", 0),
            saferadius=data.get("saferadius", 500),
            distanceradius=data.get("distanceradius", 500),
            cleanupradius=data.get("cleanupradius", 200),
            deletable=data.get("deletable", 0),
            init_random=data.get("init_random", 0),
            remove_damaged=data.get("remove_damaged", 1),
            position=data.get("position", "fixed"),
            limit=data.get("limit", "mixed"),
            active=data.get("active", 1),
        )


# ==============================================================================
# ZONE CONFIG MODEL (for cfgeventspawns.xml)
# ==============================================================================

@dataclass
class ZoneConfig:
    """
    Zone configuration for cfgeventspawns.xml.
    
    Example:
    <zone smin="1" smax="3" dmin="3" dmax="5" r="45" />
    """
    smin: int = 1
    smax: int = 3
    dmin: int = 3
    dmax: int = 5
    r: int = 45
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "smin": self.smin,
            "smax": self.smax,
            "dmin": self.dmin,
            "dmax": self.dmax,
            "r": self.r,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ZoneConfig":
        """Create from dictionary."""
        return cls(
            smin=data.get("smin", 1),
            smax=data.get("smax", 3),
            dmin=data.get("dmin", 3),
            dmax=data.get("dmax", 5),
            r=data.get("r", 45),
        )
    
    def to_xml_element(self) -> ET.Element:
        """Generate XML element."""
        zone = ET.Element("zone")
        zone.set("smin", str(self.smin))
        zone.set("smax", str(self.smax))
        zone.set("dmin", str(self.dmin))
        zone.set("dmax", str(self.dmax))
        zone.set("r", str(self.r))
        return zone


# ==============================================================================
# MAIN VEHICLE MODEL
# ==============================================================================

@dataclass
class VehicleModel:
    """
    Main vehicle model that aggregates all vehicle configurations.
    
    This is the top-level model for managing a vehicle across all config files.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    classname: str = ""  # Base model name, e.g., "Hatchback_02"
    event_name: str = ""  # Event name, e.g., "VehicleHatchback02"
    description: str = ""  # UI description (not used in XML)
    category: VehicleCategory = VehicleCategory.MODDED
    
    # Source mod info (for modded vehicles)
    mod_name: Optional[str] = None
    mod_folder: Optional[str] = None
    
    # Event configuration (events.xml)
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # Zone configuration (cfgeventspawns.xml)
    zone_config: ZoneConfig = field(default_factory=ZoneConfig)
    
    # Variants (different colors/styles)
    variants: list[VehicleVariant] = field(default_factory=list)
    
    # Spawn positions (cfgeventspawns.xml)
    spawn_positions: list[SpawnPosition] = field(default_factory=list)
    
    # Wheel/part type configurations (types.xml)
    wheel_configs: list[WheelTypeConfig] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "classname": self.classname,
            "event_name": self.event_name,
            "description": self.description,
            "category": self.category.value,
            "mod_name": self.mod_name,
            "mod_folder": self.mod_folder,
            "event_config": self.event_config.to_dict(),
            "zone_config": self.zone_config.to_dict(),
            "variants": [v.to_dict() for v in self.variants],
            "spawn_positions": [p.to_dict() for p in self.spawn_positions],
            "wheel_configs": [w.to_dict() for w in self.wheel_configs],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VehicleModel":
        """Create from dictionary."""
        vehicle = cls(
            id=data.get("id", str(uuid.uuid4())),
            classname=data.get("classname", ""),
            event_name=data.get("event_name", ""),
            description=data.get("description", ""),
            category=VehicleCategory(data.get("category", "modded")),
            mod_name=data.get("mod_name"),
            mod_folder=data.get("mod_folder"),
            event_config=EventConfig.from_dict(data.get("event_config", {})),
            zone_config=ZoneConfig.from_dict(data.get("zone_config", {})),
        )
        vehicle.variants = [VehicleVariant.from_dict(v) for v in data.get("variants", [])]
        vehicle.spawn_positions = [SpawnPosition.from_dict(p) for p in data.get("spawn_positions", [])]
        vehicle.wheel_configs = [WheelTypeConfig.from_dict(w) for w in data.get("wheel_configs", [])]
        return vehicle
    
    def to_events_xml_element(self) -> ET.Element:
        """Generate XML element for events.xml."""
        event = ET.Element("event")
        event.set("name", self.event_name)
        
        config = self.event_config
        ET.SubElement(event, "nominal").text = str(config.nominal)
        ET.SubElement(event, "min").text = str(config.min)
        ET.SubElement(event, "max").text = str(config.max)
        ET.SubElement(event, "lifetime").text = str(config.lifetime)
        ET.SubElement(event, "restock").text = str(config.restock)
        ET.SubElement(event, "saferadius").text = str(config.saferadius)
        ET.SubElement(event, "distanceradius").text = str(config.distanceradius)
        ET.SubElement(event, "cleanupradius").text = str(config.cleanupradius)
        
        # Flags
        flags = ET.SubElement(event, "flags")
        flags.set("deletable", str(config.deletable))
        flags.set("init_random", str(config.init_random))
        flags.set("remove_damaged", str(config.remove_damaged))
        
        ET.SubElement(event, "position").text = config.position
        ET.SubElement(event, "limit").text = config.limit
        ET.SubElement(event, "active").text = str(config.active)
        
        # Children (variants)
        if self.variants:
            children = ET.SubElement(event, "children")
            for variant in self.variants:
                children.append(variant.to_event_child_element())
        
        return event
    
    def to_event_spawns_xml_element(self) -> ET.Element:
        """Generate XML element for cfgeventspawns.xml."""
        event = ET.Element("event")
        event.set("name", self.event_name)
        
        # Zone config
        event.append(self.zone_config.to_xml_element())
        
        # Spawn positions
        for pos in self.spawn_positions:
            event.append(pos.to_xml_element())
        
        return event
    
    def get_all_spawnable_types_elements(self) -> list[ET.Element]:
        """Generate XML elements for cfgspawnabletypes.xml (all variants)."""
        elements = []
        for variant in self.variants:
            if variant.parts:  # Only include if has parts configured
                elements.append(variant.to_spawnable_type_element())
        return elements
    
    def get_all_wheel_type_elements(self) -> list[ET.Element]:
        """Generate XML elements for types.xml (wheel configs)."""
        return [w.to_xml_element() for w in self.wheel_configs]
    
    def clone(self) -> "VehicleModel":
        """Create a deep copy of this vehicle model."""
        return VehicleModel.from_dict(self.to_dict())


# ==============================================================================
# VEHICLE DATA STORE
# ==============================================================================

@dataclass
class VehicleDataStore:
    """
    Container for all vehicle configurations with import/export functionality.
    """
    vehicles: list[VehicleModel] = field(default_factory=list)
    version: str = "1.0"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "version": self.version,
            "vehicles": [v.to_dict() for v in self.vehicles],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VehicleDataStore":
        """Create from dictionary."""
        store = cls(version=data.get("version", "1.0"))
        store.vehicles = [VehicleModel.from_dict(v) for v in data.get("vehicles", [])]
        return store
    
    def export_to_file(self, filepath: Path) -> None:
        """Export to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def import_from_file(cls, filepath: Path) -> "VehicleDataStore":
        """Import from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def get_vanilla_vehicles(self) -> list[VehicleModel]:
        """Get all vanilla vehicles."""
        return [v for v in self.vehicles if v.category == VehicleCategory.VANILLA]
    
    def get_modded_vehicles(self) -> list[VehicleModel]:
        """Get all modded vehicles."""
        return [v for v in self.vehicles if v.category == VehicleCategory.MODDED]
    
    def get_vehicle_by_id(self, vehicle_id: str) -> Optional[VehicleModel]:
        """Get vehicle by ID."""
        for v in self.vehicles:
            if v.id == vehicle_id:
                return v
        return None
    
    def get_vehicle_by_classname(self, classname: str) -> Optional[VehicleModel]:
        """Get vehicle by classname."""
        for v in self.vehicles:
            if v.classname.lower() == classname.lower():
                return v
        return None
    
    def get_vehicle_by_event_name(self, event_name: str) -> Optional[VehicleModel]:
        """Get vehicle by event name."""
        for v in self.vehicles:
            if v.event_name.lower() == event_name.lower():
                return v
        return None
    
    def add_vehicle(self, vehicle: VehicleModel) -> None:
        """Add a vehicle to the store."""
        self.vehicles.append(vehicle)
    
    def remove_vehicle(self, vehicle_id: str) -> bool:
        """Remove a vehicle from the store."""
        for i, v in enumerate(self.vehicles):
            if v.id == vehicle_id:
                del self.vehicles[i]
                return True
        return False


# ==============================================================================
# VANILLA VEHICLE DEFINITIONS
# ==============================================================================

# List of known vanilla vehicle event names for reference
VANILLA_VEHICLE_EVENTS = [
    "VehicleOffroadHatchback",  # Ada 4x4
    "VehicleOffroad02",  # Gunter 2
    "VehicleHatchback02",  # Olga 24
    "VehicleCivilianSedan",  # Sarka 120
    "VehicleSedan02",  # Sedan
    "VehicleTruck01",  # V3S
    "VehicleBoat",  # Boat
    "VehicleTransitBus",  # Transit Bus (Livonia)
]

# List of known vanilla vehicle base classnames
VANILLA_VEHICLE_CLASSNAMES = [
    "OffroadHatchback",
    "Offroad_02",
    "Hatchback_02",
    "CivilianSedan",
    "Sedan_02",
    "Truck_01_Covered",
    "Truck_01_Chassis",
    "Boat",
    "Transit_Bus",
]


def is_vanilla_vehicle(event_name: str) -> bool:
    """Check if an event name corresponds to a vanilla vehicle."""
    return event_name in VANILLA_VEHICLE_EVENTS


def get_vanilla_vehicle_classname(event_name: str) -> Optional[str]:
    """Get the base classname for a vanilla vehicle event."""
    mapping = {
        "VehicleOffroadHatchback": "OffroadHatchback",
        "VehicleOffroad02": "Offroad_02",
        "VehicleHatchback02": "Hatchback_02",
        "VehicleCivilianSedan": "CivilianSedan",
        "VehicleSedan02": "Sedan_02",
        "VehicleTruck01": "Truck_01_Covered",
        "VehicleBoat": "Boat",
        "VehicleTransitBus": "Transit_Bus",
    }
    return mapping.get(event_name)
