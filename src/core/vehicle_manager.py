"""
Vehicle Manager - Core service for managing vehicle configurations.

This module provides functionality for:
- Parsing vehicle configurations from XML files
- Managing vehicle data (CRUD operations)
- Importing/exporting vehicle configurations
- Generating XML output for config files
- Scanning mods for vehicle configurations
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from dataclasses import dataclass, field

from src.models.vehicle_models import (
    VehicleModel, VehicleVariant, VehiclePart, SpawnPosition,
    WheelTypeConfig, EventConfig, ZoneConfig, VehicleDataStore,
    VehicleCategory, PartLabel, VANILLA_VEHICLE_EVENTS,
    is_vanilla_vehicle, get_vanilla_vehicle_classname,
)


# ==============================================================================
# XML PARSING HELPERS
# ==============================================================================

def parse_xml_file(filepath: Path) -> Optional[ET.Element]:
    """Parse an XML file and return root element."""
    try:
        tree = ET.parse(filepath)
        return tree.getroot()
    except Exception:
        return None


def get_text_or_default(element: Optional[ET.Element], default: str = "") -> str:
    """Get text content of element or default value."""
    if element is not None and element.text:
        return element.text.strip()
    return default


def get_int_or_default(element: Optional[ET.Element], default: int = 0) -> int:
    """Get integer text content of element or default value."""
    text = get_text_or_default(element)
    try:
        return int(text)
    except ValueError:
        return default


def get_float_or_default(value: Optional[str], default: float = 0.0) -> float:
    """Get float value or default."""
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# ==============================================================================
# VEHICLE PARSER - Parse from mission config files
# ==============================================================================

class VehicleConfigParser:
    """Parser for extracting vehicle configurations from mission XML files."""
    
    def __init__(self, mission_path: Path):
        """Initialize parser with mission folder path."""
        self.mission_path = mission_path
        self.db_path = mission_path / "db"
        
        # Config file paths
        self.events_xml = self.db_path / "events.xml"
        self.types_xml = self.db_path / "types.xml"
        self.cfgspawnabletypes_xml = mission_path / "cfgspawnabletypes.xml"
        self.cfgeventspawns_xml = mission_path / "cfgeventspawns.xml"
    
    def parse_all_vehicles(self) -> list[VehicleModel]:
        """Parse all vehicle configurations from mission files."""
        vehicles = []
        
        # Parse events.xml for vehicle events
        events_data = self._parse_events_xml()
        
        # Parse cfgeventspawns.xml for spawn positions
        spawns_data = self._parse_event_spawns_xml()
        
        # Parse cfgspawnabletypes.xml for vehicle parts
        spawnable_data = self._parse_spawnable_types_xml()
        
        # Parse types.xml for wheel configs
        types_data = self._parse_types_xml()
        
        # Combine data into VehicleModel objects
        for event_name, event_info in events_data.items():
            if not self._is_vehicle_event(event_name):
                continue
            
            vehicle = VehicleModel(
                classname=event_info.get("base_classname", ""),
                event_name=event_name,
                category=VehicleCategory.VANILLA if is_vanilla_vehicle(event_name) else VehicleCategory.MODDED,
                event_config=event_info.get("config", EventConfig()),
                variants=event_info.get("variants", []),
            )
            
            # Add spawn positions if available
            if event_name in spawns_data:
                vehicle.zone_config = spawns_data[event_name].get("zone", ZoneConfig())
                vehicle.spawn_positions = spawns_data[event_name].get("positions", [])
            
            # Add parts to variants from cfgspawnabletypes
            for variant in vehicle.variants:
                if variant.classname in spawnable_data:
                    variant.parts = spawnable_data[variant.classname]
            
            # Add wheel configs
            base_class = vehicle.classname or event_info.get("base_classname", "")
            if base_class:
                wheel_classname = f"{base_class}_Wheel"
                if wheel_classname in types_data:
                    vehicle.wheel_configs.append(types_data[wheel_classname])
            
            vehicles.append(vehicle)
        
        return vehicles
    
    def _is_vehicle_event(self, event_name: str) -> bool:
        """Check if an event name is a vehicle event."""
        vehicle_prefixes = ["Vehicle", "Car", "Truck", "Boat", "Bus"]
        return any(event_name.startswith(prefix) for prefix in vehicle_prefixes)
    
    def _parse_events_xml(self) -> dict:
        """Parse events.xml for vehicle event configurations."""
        result = {}
        
        if not self.events_xml.exists():
            return result
        
        root = parse_xml_file(self.events_xml)
        if root is None:
            return result
        
        for event in root.findall("event"):
            event_name = event.get("name", "")
            if not event_name:
                continue
            
            # Parse event config
            config = EventConfig(
                nominal=get_int_or_default(event.find("nominal"), 8),
                min=get_int_or_default(event.find("min"), 5),
                max=get_int_or_default(event.find("max"), 11),
                lifetime=get_int_or_default(event.find("lifetime"), 300),
                restock=get_int_or_default(event.find("restock"), 0),
                saferadius=get_int_or_default(event.find("saferadius"), 500),
                distanceradius=get_int_or_default(event.find("distanceradius"), 500),
                cleanupradius=get_int_or_default(event.find("cleanupradius"), 200),
                position=get_text_or_default(event.find("position"), "fixed"),
                limit=get_text_or_default(event.find("limit"), "mixed"),
                active=get_int_or_default(event.find("active"), 1),
            )
            
            # Parse flags
            flags = event.find("flags")
            if flags is not None:
                config.deletable = int(flags.get("deletable", 0))
                config.init_random = int(flags.get("init_random", 0))
                config.remove_damaged = int(flags.get("remove_damaged", 1))
            
            # Parse children (variants)
            variants = []
            children = event.find("children")
            base_classname = ""
            
            if children is not None:
                for child in children.findall("child"):
                    classname = child.get("type", "")
                    if not classname:
                        continue
                    
                    # First variant typically has the base classname
                    if not base_classname:
                        # Try to extract base classname (remove color suffix)
                        parts = classname.rsplit("_", 1)
                        if len(parts) > 1 and parts[1] in ["Black", "Blue", "Red", "Green", "Yellow", "White", "Orange", "Grey", "Wine"]:
                            base_classname = parts[0]
                        else:
                            base_classname = classname
                    
                    variant = VehicleVariant(
                        classname=classname,
                        min_spawn=int(child.get("min", 3)),
                        max_spawn=int(child.get("max", 5)),
                        loot_min=int(child.get("lootmin", 0)),
                        loot_max=int(child.get("lootmax", 0)),
                    )
                    variants.append(variant)
            
            result[event_name] = {
                "config": config,
                "variants": variants,
                "base_classname": base_classname,
            }
        
        return result
    
    def _parse_event_spawns_xml(self) -> dict:
        """Parse cfgeventspawns.xml for spawn positions."""
        result = {}
        
        if not self.cfgeventspawns_xml.exists():
            return result
        
        root = parse_xml_file(self.cfgeventspawns_xml)
        if root is None:
            return result
        
        for event in root.findall("event"):
            event_name = event.get("name", "")
            if not event_name:
                continue
            
            # Parse zone config
            zone = ZoneConfig()
            zone_elem = event.find("zone")
            if zone_elem is not None:
                zone = ZoneConfig(
                    smin=int(zone_elem.get("smin", 1)),
                    smax=int(zone_elem.get("smax", 3)),
                    dmin=int(zone_elem.get("dmin", 3)),
                    dmax=int(zone_elem.get("dmax", 5)),
                    r=int(zone_elem.get("r", 45)),
                )
            
            # Parse positions
            positions = []
            for pos_elem in event.findall("pos"):
                pos = SpawnPosition(
                    x=get_float_or_default(pos_elem.get("x")),
                    y=get_float_or_default(pos_elem.get("y")) if pos_elem.get("y") else None,
                    z=get_float_or_default(pos_elem.get("z")),
                    a=get_float_or_default(pos_elem.get("a")),
                    is_custom=False,  # Positions from file are not custom initially
                )
                positions.append(pos)
            
            result[event_name] = {
                "zone": zone,
                "positions": positions,
            }
        
        return result
    
    def _parse_spawnable_types_xml(self) -> dict[str, list[VehiclePart]]:
        """Parse cfgspawnabletypes.xml for vehicle parts."""
        result = {}
        
        if not self.cfgspawnabletypes_xml.exists():
            return result
        
        root = parse_xml_file(self.cfgspawnabletypes_xml)
        if root is None:
            return result
        
        for type_elem in root.findall("type"):
            type_name = type_elem.get("name", "")
            if not type_name:
                continue
            
            parts = []
            for attachments in type_elem.findall("attachments"):
                attachment_chance = get_float_or_default(attachments.get("chance"), 1.0)
                
                for item in attachments.findall("item"):
                    item_name = item.get("name", "")
                    if not item_name:
                        continue
                    
                    part = VehiclePart(
                        classname=item_name,
                        chance=get_float_or_default(item.get("chance"), 1.0),
                        attachment_chance=attachment_chance,
                        label=self._guess_part_label(item_name),
                    )
                    parts.append(part)
            
            if parts:
                result[type_name] = parts
        
        return result
    
    def _parse_types_xml(self) -> dict[str, WheelTypeConfig]:
        """Parse types.xml for wheel/part spawn configurations."""
        result = {}
        
        if not self.types_xml.exists():
            return result
        
        root = parse_xml_file(self.types_xml)
        if root is None:
            return result
        
        # Look for wheel-related types
        for type_elem in root.findall("type"):
            type_name = type_elem.get("name", "")
            if not type_name or not self._is_vehicle_part_type(type_name):
                continue
            
            config = WheelTypeConfig(
                classname=type_name,
                nominal=get_int_or_default(type_elem.find("nominal"), 40),
                min=get_int_or_default(type_elem.find("min"), 30),
                lifetime=get_int_or_default(type_elem.find("lifetime"), 28800),
                restock=get_int_or_default(type_elem.find("restock"), 0),
                quantmin=get_int_or_default(type_elem.find("quantmin"), -1),
                quantmax=get_int_or_default(type_elem.find("quantmax"), -1),
                cost=get_int_or_default(type_elem.find("cost"), 100),
            )
            
            # Parse flags
            flags = type_elem.find("flags")
            if flags is not None:
                config.count_in_cargo = int(flags.get("count_in_cargo", 0))
                config.count_in_hoarder = int(flags.get("count_in_hoarder", 0))
                config.count_in_map = int(flags.get("count_in_map", 1))
                config.count_in_player = int(flags.get("count_in_player", 0))
                config.crafted = int(flags.get("crafted", 0))
                config.deloot = int(flags.get("deloot", 0))
            
            # Parse category
            category = type_elem.find("category")
            if category is not None:
                config.category = category.get("name", "lootdispatch")
            
            # Parse tags
            config.tags = [t.get("name", "") for t in type_elem.findall("tag") if t.get("name")]
            
            # Parse usages
            config.usages = [u.get("name", "") for u in type_elem.findall("usage") if u.get("name")]
            
            # Parse values
            config.values = [v.get("name", "") for v in type_elem.findall("value") if v.get("name")]
            
            result[type_name] = config
        
        return result
    
    def _is_vehicle_part_type(self, type_name: str) -> bool:
        """Check if a type name is a vehicle part (wheel, door, hood, etc)."""
        part_patterns = [
            r"_Wheel$", r"_Door_", r"_Hood$", r"_Trunk$",
            r"_Front_", r"_Rear_", r"_Fender",
        ]
        return any(re.search(pattern, type_name) for pattern in part_patterns)
    
    def _guess_part_label(self, part_name: str) -> PartLabel:
        """Guess the part label based on classname."""
        name_lower = part_name.lower()
        
        if "wheel" in name_lower:
            if "spare" in name_lower:
                return PartLabel.SPARE_WHEEL
            return PartLabel.WHEEL
        elif "sparkplug" in name_lower:
            return PartLabel.SPARK_PLUG
        elif "glowplug" in name_lower:
            return PartLabel.GLOW_PLUG
        elif "battery" in name_lower:
            return PartLabel.BATTERY
        elif "radiator" in name_lower:
            return PartLabel.RADIATOR
        elif "headlight" in name_lower:
            return PartLabel.HEADLIGHT
        elif "door" in name_lower:
            return PartLabel.DOOR
        elif "hood" in name_lower:
            return PartLabel.HOOD
        elif "trunk" in name_lower:
            return PartLabel.TRUNK
        elif "fuel" in name_lower or "tank" in name_lower:
            return PartLabel.FUEL_TANK
        elif "engine" in name_lower:
            return PartLabel.ENGINE
        
        return PartLabel.OTHER


# ==============================================================================
# VEHICLE MANAGER - Main service class
# ==============================================================================

class VehicleManager:
    """
    Main service for managing vehicle configurations.
    
    Handles:
    - Loading/saving vehicle data
    - CRUD operations on vehicles
    - Import/export functionality
    - XML generation for config files
    """
    
    def __init__(self, mission_path: Path):
        """Initialize vehicle manager with mission path."""
        self.mission_path = mission_path
        self.db_path = mission_path / "db"
        self.data_store = VehicleDataStore()
        self._storage_file = mission_path / "vehicle_manager_data.json"
        
        # Config file paths
        self.events_xml = self.db_path / "events.xml"
        self.types_xml = self.db_path / "types.xml"
        self.cfgspawnabletypes_xml = mission_path / "cfgspawnabletypes.xml"
        self.cfgeventspawns_xml = mission_path / "cfgeventspawns.xml"
    
    def load_data(self) -> bool:
        """Load vehicle data from storage file."""
        if self._storage_file.exists():
            try:
                self.data_store = VehicleDataStore.import_from_file(self._storage_file)
                return True
            except Exception:
                pass
        return False
    
    def save_data(self) -> bool:
        """Save vehicle data to storage file."""
        try:
            self.data_store.export_to_file(self._storage_file)
            return True
        except Exception:
            return False
    
    def scan_existing_vehicles(self) -> list[VehicleModel]:
        """Scan mission files for existing vehicle configurations."""
        parser = VehicleConfigParser(self.mission_path)
        return parser.parse_all_vehicles()
    
    def import_vehicles_from_scan(self, vehicles: list[VehicleModel]) -> int:
        """Import scanned vehicles into data store (merge/update)."""
        imported = 0
        for vehicle in vehicles:
            existing = self.data_store.get_vehicle_by_event_name(vehicle.event_name)
            if existing:
                # Update existing vehicle
                existing.variants = vehicle.variants
                existing.spawn_positions = vehicle.spawn_positions
                existing.event_config = vehicle.event_config
                existing.zone_config = vehicle.zone_config
                existing.wheel_configs = vehicle.wheel_configs
            else:
                # Add new vehicle
                self.data_store.add_vehicle(vehicle)
                imported += 1
        return imported
    
    def get_vanilla_vehicles(self) -> list[VehicleModel]:
        """Get all vanilla vehicles."""
        return self.data_store.get_vanilla_vehicles()
    
    def get_modded_vehicles(self) -> list[VehicleModel]:
        """Get all modded vehicles."""
        return self.data_store.get_modded_vehicles()
    
    def get_all_vehicles(self) -> list[VehicleModel]:
        """Get all vehicles."""
        return self.data_store.vehicles
    
    def add_vehicle(self, vehicle: VehicleModel) -> bool:
        """Add a new vehicle."""
        # Check for duplicate
        if self.data_store.get_vehicle_by_event_name(vehicle.event_name):
            return False
        self.data_store.add_vehicle(vehicle)
        return True
    
    def update_vehicle(self, vehicle: VehicleModel) -> bool:
        """Update an existing vehicle."""
        existing = self.data_store.get_vehicle_by_id(vehicle.id)
        if existing:
            # Update all fields
            idx = self.data_store.vehicles.index(existing)
            self.data_store.vehicles[idx] = vehicle
            return True
        return False
    
    def delete_vehicle(self, vehicle_id: str) -> bool:
        """Delete a vehicle."""
        return self.data_store.remove_vehicle(vehicle_id)
    
    def get_vehicle(self, vehicle_id: str) -> Optional[VehicleModel]:
        """Get a vehicle by ID."""
        return self.data_store.get_vehicle_by_id(vehicle_id)
    
    def export_vehicle(self, vehicle_id: str, filepath: Path) -> bool:
        """Export a single vehicle to JSON file."""
        vehicle = self.data_store.get_vehicle_by_id(vehicle_id)
        if not vehicle:
            return False
        
        try:
            data = {
                "version": "1.0",
                "vehicle": vehicle.to_dict(),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def import_vehicle(self, filepath: Path) -> Optional[VehicleModel]:
        """Import a vehicle from JSON file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            vehicle_data = data.get("vehicle", data)
            vehicle = VehicleModel.from_dict(vehicle_data)
            
            # Check for duplicate and rename if needed
            base_name = vehicle.event_name
            counter = 1
            while self.data_store.get_vehicle_by_event_name(vehicle.event_name):
                vehicle.event_name = f"{base_name}_{counter}"
                counter += 1
            
            self.data_store.add_vehicle(vehicle)
            return vehicle
        except Exception:
            return None
    
    def export_all_vehicles(self, filepath: Path) -> bool:
        """Export all vehicles to JSON file."""
        try:
            self.data_store.export_to_file(filepath)
            return True
        except Exception:
            return False
    
    def import_all_vehicles(self, filepath: Path, merge: bool = True) -> int:
        """Import vehicles from JSON file."""
        try:
            store = VehicleDataStore.import_from_file(filepath)
            
            if not merge:
                self.data_store = store
                return len(store.vehicles)
            
            # Merge vehicles
            imported = 0
            for vehicle in store.vehicles:
                existing = self.data_store.get_vehicle_by_event_name(vehicle.event_name)
                if not existing:
                    self.data_store.add_vehicle(vehicle)
                    imported += 1
            
            return imported
        except Exception:
            return 0
    
    # ==========================================================================
    # XML GENERATION
    # ==========================================================================
    
    def generate_events_xml(self, vehicles: Optional[list[VehicleModel]] = None) -> str:
        """Generate events.xml content for vehicles."""
        if vehicles is None:
            vehicles = self.data_store.vehicles
        
        root = ET.Element("events")
        
        for vehicle in vehicles:
            if vehicle.variants:  # Only include vehicles with variants
                root.append(vehicle.to_events_xml_element())
        
        return self._prettify_xml(root)
    
    def generate_event_spawns_xml(self, vehicles: Optional[list[VehicleModel]] = None) -> str:
        """Generate cfgeventspawns.xml content for vehicles."""
        if vehicles is None:
            vehicles = self.data_store.vehicles
        
        root = ET.Element("eventposdef")
        
        for vehicle in vehicles:
            if vehicle.spawn_positions:  # Only include vehicles with spawn positions
                root.append(vehicle.to_event_spawns_xml_element())
        
        return self._prettify_xml(root)
    
    def generate_spawnable_types_xml(self, vehicles: Optional[list[VehicleModel]] = None) -> str:
        """Generate cfgspawnabletypes.xml content for vehicles."""
        if vehicles is None:
            vehicles = self.data_store.vehicles
        
        root = ET.Element("spawnabletypes")
        
        for vehicle in vehicles:
            for elem in vehicle.get_all_spawnable_types_elements():
                root.append(elem)
        
        return self._prettify_xml(root)
    
    def generate_types_xml(self, vehicles: Optional[list[VehicleModel]] = None) -> str:
        """Generate types.xml content for vehicle wheels/parts."""
        if vehicles is None:
            vehicles = self.data_store.vehicles
        
        root = ET.Element("types")
        
        for vehicle in vehicles:
            for elem in vehicle.get_all_wheel_type_elements():
                root.append(elem)
        
        return self._prettify_xml(root)
    
    def _prettify_xml(self, elem: ET.Element, indent: str = "    ") -> str:
        """Return a pretty-printed XML string."""
        from xml.dom import minidom
        
        rough_string = ET.tostring(elem, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        pretty = reparsed.toprettyxml(indent=indent)
        
        # Remove extra blank lines and XML declaration
        lines = [line for line in pretty.split('\n') if line.strip()]
        if lines and lines[0].startswith('<?xml'):
            lines = lines[1:]
        
        return '\n'.join(lines)
    
    # ==========================================================================
    # APPLY TO CONFIG FILES
    # ==========================================================================
    
    def apply_to_events_xml(self, vehicles: list[VehicleModel], backup: bool = True) -> bool:
        """Apply vehicle configurations to events.xml."""
        if not self.events_xml.exists():
            return False
        
        try:
            # Create backup
            if backup:
                self._create_backup(self.events_xml)
            
            # Parse existing file
            tree = ET.parse(self.events_xml)
            root = tree.getroot()
            
            # Remove existing vehicle events
            event_names = {v.event_name for v in vehicles}
            for event in root.findall("event"):
                if event.get("name") in event_names:
                    root.remove(event)
            
            # Add new vehicle events
            for vehicle in vehicles:
                if vehicle.variants:
                    root.append(vehicle.to_events_xml_element())
            
            # Write back
            tree.write(self.events_xml, encoding="utf-8", xml_declaration=True)
            return True
        except Exception:
            return False
    
    def apply_to_event_spawns_xml(self, vehicles: list[VehicleModel], backup: bool = True) -> bool:
        """Apply vehicle configurations to cfgeventspawns.xml."""
        if not self.cfgeventspawns_xml.exists():
            return False
        
        try:
            # Create backup
            if backup:
                self._create_backup(self.cfgeventspawns_xml)
            
            # Parse existing file
            tree = ET.parse(self.cfgeventspawns_xml)
            root = tree.getroot()
            
            # Remove existing vehicle events
            event_names = {v.event_name for v in vehicles}
            for event in root.findall("event"):
                if event.get("name") in event_names:
                    root.remove(event)
            
            # Add new vehicle events
            for vehicle in vehicles:
                if vehicle.spawn_positions:
                    root.append(vehicle.to_event_spawns_xml_element())
            
            # Write back
            tree.write(self.cfgeventspawns_xml, encoding="utf-8", xml_declaration=True)
            return True
        except Exception:
            return False
    
    def apply_to_spawnable_types_xml(self, vehicles: list[VehicleModel], backup: bool = True) -> bool:
        """Apply vehicle configurations to cfgspawnabletypes.xml."""
        if not self.cfgspawnabletypes_xml.exists():
            return False
        
        try:
            # Create backup
            if backup:
                self._create_backup(self.cfgspawnabletypes_xml)
            
            # Parse existing file
            tree = ET.parse(self.cfgspawnabletypes_xml)
            root = tree.getroot()
            
            # Get all variant classnames
            variant_names = set()
            for vehicle in vehicles:
                for variant in vehicle.variants:
                    variant_names.add(variant.classname)
            
            # Remove existing types
            for type_elem in root.findall("type"):
                if type_elem.get("name") in variant_names:
                    root.remove(type_elem)
            
            # Add new types
            for vehicle in vehicles:
                for elem in vehicle.get_all_spawnable_types_elements():
                    root.append(elem)
            
            # Write back
            tree.write(self.cfgspawnabletypes_xml, encoding="utf-8", xml_declaration=True)
            return True
        except Exception:
            return False
    
    def apply_to_types_xml(self, vehicles: list[VehicleModel], backup: bool = True) -> bool:
        """Apply wheel configurations to types.xml."""
        if not self.types_xml.exists():
            return False
        
        try:
            # Create backup
            if backup:
                self._create_backup(self.types_xml)
            
            # Parse existing file
            tree = ET.parse(self.types_xml)
            root = tree.getroot()
            
            # Get all wheel classnames
            wheel_names = set()
            for vehicle in vehicles:
                for wheel in vehicle.wheel_configs:
                    wheel_names.add(wheel.classname)
            
            # Remove existing types
            for type_elem in root.findall("type"):
                if type_elem.get("name") in wheel_names:
                    root.remove(type_elem)
            
            # Add new types
            for vehicle in vehicles:
                for elem in vehicle.get_all_wheel_type_elements():
                    root.append(elem)
            
            # Write back
            tree.write(self.types_xml, encoding="utf-8", xml_declaration=True)
            return True
        except Exception:
            return False
    
    def apply_all(self, vehicles: list[VehicleModel], backup: bool = True) -> dict[str, bool]:
        """Apply vehicle configurations to all config files."""
        return {
            "events.xml": self.apply_to_events_xml(vehicles, backup),
            "cfgeventspawns.xml": self.apply_to_event_spawns_xml(vehicles, backup),
            "cfgspawnabletypes.xml": self.apply_to_spawnable_types_xml(vehicles, backup),
            "types.xml": self.apply_to_types_xml(vehicles, backup),
        }
    
    def _create_backup(self, filepath: Path) -> bool:
        """Create a backup of a file."""
        try:
            backup_path = filepath.with_suffix(filepath.suffix + ".bak")
            import shutil
            shutil.copy2(filepath, backup_path)
            return True
        except Exception:
            return False
    
    # ==========================================================================
    # VANILLA SPAWN POSITION BORROWING
    # ==========================================================================
    
    def get_available_vanilla_positions(self, exclude_event: Optional[str] = None) -> dict[str, list[SpawnPosition]]:
        """Get available spawn positions from vanilla vehicles."""
        result = {}
        
        for vehicle in self.data_store.get_vanilla_vehicles():
            if exclude_event and vehicle.event_name == exclude_event:
                continue
            
            if vehicle.spawn_positions:
                result[vehicle.event_name] = vehicle.spawn_positions
        
        return result
    
    def borrow_positions_from_vanilla(
        self, 
        target_vehicle: VehicleModel, 
        source_event: str, 
        position_ids: list[str]
    ) -> int:
        """Borrow spawn positions from a vanilla vehicle."""
        source_vehicle = self.data_store.get_vehicle_by_event_name(source_event)
        if not source_vehicle:
            return 0
        
        borrowed = 0
        existing_keys = {p.get_key() for p in target_vehicle.spawn_positions}
        for pos in source_vehicle.spawn_positions:
            if pos.id in position_ids:
                # Create a copy for the target
                new_pos = SpawnPosition(
                    x=pos.x,
                    y=pos.y,
                    z=pos.z,
                    a=pos.a,
                    borrowed_from=source_event,
                    is_custom=False,
                )
                key = new_pos.get_key()
                if key in existing_keys:
                    continue
                target_vehicle.spawn_positions.append(new_pos)
                existing_keys.add(key)
                borrowed += 1
        
        return borrowed
    
    def return_borrowed_positions(self, vehicle: VehicleModel) -> int:
        """Remove all borrowed positions from a vehicle."""
        original_count = len(vehicle.spawn_positions)
        vehicle.spawn_positions = [
            p for p in vehicle.spawn_positions if p.is_custom
        ]
        return original_count - len(vehicle.spawn_positions)


# ==============================================================================
# MOD SCANNER - Scan mods for vehicle configurations
# ==============================================================================

class ModVehicleScanner:
    """Scanner for finding vehicle configurations in installed mods."""
    
    def __init__(self, mods_path: Path):
        """Initialize scanner with mods folder path."""
        self.mods_path = mods_path
    
    def scan_mod(self, mod_folder: Path) -> list[dict]:
        """Scan a single mod for vehicle configurations."""
        results = []
        
        # Common locations for vehicle configs
        config_locations = [
            mod_folder / "types.xml",
            mod_folder / "cfgspawnabletypes.xml", 
            mod_folder / "cfgeventspawns.xml",
            mod_folder / "events.xml",
        ]
        
        for location in config_locations:
            if location.exists():
                result = self._parse_config_file(location)
                if result:
                    results.append(result)
        
        # Also check subdirectories
        for subdir in ["db", "config", "configs"]:
            subpath = mod_folder / subdir
            if subpath.exists():
                for xml_file in subpath.glob("*.xml"):
                    result = self._parse_config_file(xml_file)
                    if result:
                        results.append(result)
        
        return results
    
    def scan_all_mods(self) -> dict[str, list[dict]]:
        """Scan all mods for vehicle configurations."""
        results = {}
        
        if not self.mods_path.exists():
            return results
        
        for mod_folder in self.mods_path.iterdir():
            if mod_folder.is_dir() and mod_folder.name.startswith("@"):
                mod_results = self.scan_mod(mod_folder)
                if mod_results:
                    results[mod_folder.name] = mod_results
        
        return results
    
    def _parse_config_file(self, filepath: Path) -> Optional[dict]:
        """Parse a config file and extract vehicle-related entries."""
        root = parse_xml_file(filepath)
        if root is None:
            return None
        
        result = {
            "file": str(filepath),
            "filename": filepath.name,
            "root_element": root.tag,
            "entries": [],
        }
        
        # Look for vehicle-related entries based on root element
        if root.tag == "events":
            for event in root.findall("event"):
                name = event.get("name", "")
                if self._is_vehicle_entry(name):
                    result["entries"].append({
                        "type": "event",
                        "name": name,
                        "element": event,
                    })
        
        elif root.tag == "eventposdef":
            for event in root.findall("event"):
                name = event.get("name", "")
                if self._is_vehicle_entry(name):
                    result["entries"].append({
                        "type": "eventspawn",
                        "name": name,
                        "element": event,
                    })
        
        elif root.tag in ["spawnabletypes", "types"]:
            for type_elem in root.findall("type"):
                name = type_elem.get("name", "")
                # Vehicle parts or vehicle types
                if self._is_vehicle_entry(name) or self._is_vehicle_part(name):
                    result["entries"].append({
                        "type": root.tag,
                        "name": name,
                        "element": type_elem,
                    })
        
        return result if result["entries"] else None
    
    def _is_vehicle_entry(self, name: str) -> bool:
        """Check if entry name is vehicle-related."""
        vehicle_prefixes = ["Vehicle", "Car", "Truck", "Boat", "Bus", "Bike", "Motorcycle"]
        return any(name.startswith(prefix) for prefix in vehicle_prefixes)
    
    def _is_vehicle_part(self, name: str) -> bool:
        """Check if entry name is a vehicle part."""
        part_patterns = [
            r"_Wheel$", r"_Door_", r"_Hood$", r"_Trunk$",
            r"_Front_", r"_Rear_", r"_Fender", r"Hatchback",
            r"Sedan", r"Offroad", r"Truck", r"Transit",
        ]
        return any(re.search(pattern, name, re.IGNORECASE) for pattern in part_patterns)
