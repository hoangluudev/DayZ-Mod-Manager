"""
Vehicle Manager Dialog - Main UI for managing vehicle configurations.

Provides:
- List of vanilla/modded vehicles (2 tabs)
- Add, Edit, Delete, Import, Export functionality
- Detailed configuration for each vehicle:
  - Variants (colors/styles)
  - Parts/attachments per variant
  - Spawn positions
  - Wheel/part spawn configs
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QListWidget, QListWidgetItem,
    QMessageBox, QFileDialog, QSplitter, QGroupBox,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTextEdit, QScrollArea,
    QFrame, QStackedWidget, QToolButton, QMenu, QSizePolicy,
    QDialogButtonBox, QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

from src.utils.locale_manager import tr
from src.ui.widgets import IconButton
from src.ui.theme_manager import ThemeManager
from src.core.vehicle_manager import VehicleManager, ModVehicleScanner
from src.models.vehicle_models import (
    VehicleModel, VehicleVariant, VehiclePart, SpawnPosition,
    WheelTypeConfig, EventConfig, ZoneConfig, VehicleCategory,
    PartLabel, VehicleDataStore,
)


# ==============================================================================
# CONSTANTS
# ==============================================================================

PART_LABEL_NAMES = {
    PartLabel.WHEEL: "Wheel",
    PartLabel.SPARE_WHEEL: "Spare Wheel",
    PartLabel.SPARK_PLUG: "Spark Plug",
    PartLabel.GLOW_PLUG: "Glow Plug",
    PartLabel.BATTERY: "Battery",
    PartLabel.RADIATOR: "Radiator",
    PartLabel.HEADLIGHT: "Headlight",
    PartLabel.DOOR: "Door",
    PartLabel.HOOD: "Hood",
    PartLabel.TRUNK: "Trunk",
    PartLabel.FUEL_TANK: "Fuel Tank",
    PartLabel.ENGINE: "Engine",
    PartLabel.OTHER: "Other",
}


# ==============================================================================
# MAIN VEHICLE MANAGER DIALOG
# ==============================================================================

class VehicleManagerDialog(QDialog):
    """Main dialog for managing vehicle configurations."""
    
    vehicles_changed = Signal()  # Emitted when vehicles are modified
    
    def __init__(self, server_path: Path, mission_template: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.server_path = server_path
        self.mission_template = mission_template
        self.mission_path = server_path / "mpmissions" / mission_template
        
        # Initialize vehicle manager
        self.vehicle_manager = VehicleManager(self.mission_path)
        loaded_from_disk = self.vehicle_manager.load_data()
        
        self._selected_vehicle: Optional[VehicleModel] = None
        
        self._setup_ui()
        self.setWindowTitle(tr("vehicle_manager.title"))
        self.setMinimumSize(1400, 850)
        self.resize(1600, 900)
        
        # Load initial data
        self._refresh_vehicle_lists()

        # Auto-load vehicles from mission config files on first open (no prompts).
        # Only does this when there is no saved vehicle_manager_data.json yet.
        if (not loaded_from_disk) and (len(self.vehicle_manager.get_all_vehicles()) == 0):
            QTimer.singleShot(0, self._auto_load_from_mission)

    def _auto_load_from_mission(self):
        """Populate data store by scanning mission configs (silent)."""
        try:
            vehicles = self.vehicle_manager.scan_existing_vehicles()
            if not vehicles:
                return
            self.vehicle_manager.import_vehicles_from_scan(vehicles)
            # Best-effort persistence so next open is instant.
            self.vehicle_manager.save_data()
            self._refresh_vehicle_lists()
        except Exception:
            # Silent by design; user can still click Scan to troubleshoot.
            return
    
    def _setup_ui(self):
        """Setup the main UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        self._create_header(layout)
        
        # Main content - splitter with vehicle list left, details right
        self._create_main_content(layout)
        
        # Footer with action buttons
        self._create_footer(layout)
    
    def _create_header(self, layout: QVBoxLayout):
        """Create header with title and action buttons."""
        header = QHBoxLayout()
        
        title = QLabel(f"<h2>{tr('vehicle_manager.title')}</h2>")
        header.addWidget(title)
        
        header.addStretch()
        
        # Scan button
        self.btn_scan = IconButton("refresh", tr("vehicle_manager.scan_existing"), size=16)
        self.btn_scan.clicked.connect(self._scan_existing_vehicles)
        header.addWidget(self.btn_scan)
        
        # Import button
        self.btn_import = IconButton("folder", tr("vehicle_manager.import_vehicles"), size=16)
        self.btn_import.clicked.connect(self._import_vehicles)
        header.addWidget(self.btn_import)
        
        # Export button
        self.btn_export = IconButton("save", tr("vehicle_manager.export_vehicles"), size=16)
        self.btn_export.clicked.connect(self._export_vehicles)
        header.addWidget(self.btn_export)
        
        layout.addLayout(header)
        
        # Mission path info
        lbl_mission = QLabel(f"{tr('vehicle_manager.mission_folder')}: {self.mission_path}")
        lbl_mission.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(lbl_mission)
    
    def _create_main_content(self, layout: QVBoxLayout):
        """Create main content area."""
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Vehicle list with tabs
        left_widget = self._create_vehicle_list_panel()
        splitter.addWidget(left_widget)
        
        # Right: Vehicle details
        right_widget = self._create_vehicle_details_panel()
        splitter.addWidget(right_widget)
        
        # Set splitter sizes (35% left, 65% right)
        splitter.setStretchFactor(0, 35)
        splitter.setStretchFactor(1, 65)
        splitter.setSizes([450, 850])
        
        layout.addWidget(splitter, stretch=1)
    
    def _create_vehicle_list_panel(self) -> QWidget:
        """Create vehicle list panel with vanilla/modded tabs."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with add button
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{tr('vehicle_manager.vehicles')}</b>"))
        header.addStretch()
        
        self.btn_add_vehicle = IconButton("plus", tr("vehicle_manager.add_vehicle"), size=14)
        self.btn_add_vehicle.clicked.connect(self._add_vehicle)
        header.addWidget(self.btn_add_vehicle)
        
        layout.addLayout(header)
        
        # Tabs for vanilla/modded
        self.vehicle_tabs = QTabWidget()
        
        # Vanilla tab
        self.list_vanilla = QListWidget()
        self.list_vanilla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_vanilla.itemClicked.connect(self._on_vehicle_selected)
        self.list_vanilla.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_vanilla.customContextMenuRequested.connect(self._show_vehicle_context_menu)
        self.vehicle_tabs.addTab(self.list_vanilla, tr("vehicle_manager.tab_vanilla"))
        
        # Modded tab
        self.list_modded = QListWidget()
        self.list_modded.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_modded.itemClicked.connect(self._on_vehicle_selected)
        self.list_modded.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_modded.customContextMenuRequested.connect(self._show_vehicle_context_menu)
        self.vehicle_tabs.addTab(self.list_modded, tr("vehicle_manager.tab_modded"))
        
        layout.addWidget(self.vehicle_tabs)
        
        return widget
    
    def _create_vehicle_details_panel(self) -> QWidget:
        """Create vehicle details panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget for empty state and details
        self.details_stack = QStackedWidget()
        
        # Empty state
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.addStretch()
        lbl_empty = QLabel(tr("vehicle_manager.select_vehicle"))
        lbl_empty.setAlignment(Qt.AlignCenter)
        lbl_empty.setStyleSheet("color: gray; font-size: 14px;")
        empty_layout.addWidget(lbl_empty)
        empty_layout.addStretch()
        self.details_stack.addWidget(empty_widget)
        
        # Details view
        details_widget = self._create_details_view()
        self.details_stack.addWidget(details_widget)
        
        layout.addWidget(self.details_stack)
        
        return widget
    
    def _create_details_view(self) -> QWidget:
        """Create the vehicle details view with tabs."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Vehicle info header
        info_header = QHBoxLayout()
        
        self.lbl_vehicle_name = QLabel("<b>Vehicle Name</b>")
        self.lbl_vehicle_name.setStyleSheet("font-size: 16px;")
        info_header.addWidget(self.lbl_vehicle_name)
        
        info_header.addStretch()
        
        # Delete button
        self.btn_delete_vehicle = IconButton("trash", tr("common.delete"), size=14)
        self.btn_delete_vehicle.clicked.connect(self._delete_selected_vehicle)
        info_header.addWidget(self.btn_delete_vehicle)
        
        # Export single vehicle
        self.btn_export_single = IconButton("save", tr("vehicle_manager.export_single"), size=14)
        self.btn_export_single.clicked.connect(self._export_single_vehicle)
        info_header.addWidget(self.btn_export_single)
        
        layout.addLayout(info_header)
        
        # Tabs for different config aspects
        self.detail_tabs = QTabWidget()
        
        # Tab 1: Basic Info & Event Config
        self.tab_basic = self._create_basic_info_tab()
        self.detail_tabs.addTab(self.tab_basic, tr("vehicle_manager.tab_basic"))
        
        # Tab 2: Variants
        self.tab_variants = self._create_variants_tab()
        self.detail_tabs.addTab(self.tab_variants, tr("vehicle_manager.tab_variants"))
        
        # Tab 3: Parts (per variant)
        self.tab_parts = self._create_parts_tab()
        self.detail_tabs.addTab(self.tab_parts, tr("vehicle_manager.tab_parts"))
        
        # Tab 4: Spawn Positions
        self.tab_spawns = self._create_spawns_tab()
        self.detail_tabs.addTab(self.tab_spawns, tr("vehicle_manager.tab_spawns"))
        
        # Tab 5: Wheel Config (types.xml)
        self.tab_wheels = self._create_wheels_tab()
        self.detail_tabs.addTab(self.tab_wheels, tr("vehicle_manager.tab_wheels"))
        
        # Tab 6: XML Preview
        self.tab_preview = self._create_preview_tab()
        self.detail_tabs.addTab(self.tab_preview, tr("vehicle_manager.tab_preview"))
        
        layout.addWidget(self.detail_tabs)
        
        return widget
    
    def _create_basic_info_tab(self) -> QWidget:
        """Create basic info and event config tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Basic info group
        basic_group = QGroupBox(tr("vehicle_manager.basic_info"))
        basic_layout = QFormLayout(basic_group)
        
        self.txt_classname = QLineEdit()
        self.txt_classname.setPlaceholderText("e.g., Hatchback_02")
        basic_layout.addRow(tr("vehicle_manager.classname"), self.txt_classname)
        
        self.txt_event_name = QLineEdit()
        self.txt_event_name.setPlaceholderText("e.g., VehicleHatchback02")
        basic_layout.addRow(tr("vehicle_manager.event_name"), self.txt_event_name)
        
        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText(tr("vehicle_manager.description_hint"))
        basic_layout.addRow(tr("vehicle_manager.description"), self.txt_description)
        
        self.cmb_category = QComboBox()
        self.cmb_category.addItem(tr("vehicle_manager.category_vanilla"), VehicleCategory.VANILLA.value)
        self.cmb_category.addItem(tr("vehicle_manager.category_modded"), VehicleCategory.MODDED.value)
        basic_layout.addRow(tr("vehicle_manager.category"), self.cmb_category)
        
        self.txt_mod_name = QLineEdit()
        self.txt_mod_name.setPlaceholderText(tr("vehicle_manager.mod_name_hint"))
        basic_layout.addRow(tr("vehicle_manager.mod_name"), self.txt_mod_name)
        
        layout.addWidget(basic_group)
        
        # Event config group
        event_group = QGroupBox(tr("vehicle_manager.event_config"))
        event_layout = QGridLayout(event_group)
        
        row = 0
        self.spin_nominal = QSpinBox()
        self.spin_nominal.setRange(0, 100)
        self.spin_nominal.setValue(8)
        event_layout.addWidget(QLabel("nominal:"), row, 0)
        event_layout.addWidget(self.spin_nominal, row, 1)
        
        self.spin_min = QSpinBox()
        self.spin_min.setRange(0, 100)
        self.spin_min.setValue(5)
        event_layout.addWidget(QLabel("min:"), row, 2)
        event_layout.addWidget(self.spin_min, row, 3)
        
        self.spin_max = QSpinBox()
        self.spin_max.setRange(0, 100)
        self.spin_max.setValue(11)
        event_layout.addWidget(QLabel("max:"), row, 4)
        event_layout.addWidget(self.spin_max, row, 5)
        
        row += 1
        self.spin_lifetime = QSpinBox()
        self.spin_lifetime.setRange(0, 999999)
        self.spin_lifetime.setValue(300)
        event_layout.addWidget(QLabel("lifetime:"), row, 0)
        event_layout.addWidget(self.spin_lifetime, row, 1)
        
        self.spin_restock = QSpinBox()
        self.spin_restock.setRange(0, 999999)
        self.spin_restock.setValue(0)
        event_layout.addWidget(QLabel("restock:"), row, 2)
        event_layout.addWidget(self.spin_restock, row, 3)
        
        row += 1
        self.spin_saferadius = QSpinBox()
        self.spin_saferadius.setRange(0, 9999)
        self.spin_saferadius.setValue(500)
        event_layout.addWidget(QLabel("saferadius:"), row, 0)
        event_layout.addWidget(self.spin_saferadius, row, 1)
        
        self.spin_distanceradius = QSpinBox()
        self.spin_distanceradius.setRange(0, 9999)
        self.spin_distanceradius.setValue(500)
        event_layout.addWidget(QLabel("distanceradius:"), row, 2)
        event_layout.addWidget(self.spin_distanceradius, row, 3)
        
        self.spin_cleanupradius = QSpinBox()
        self.spin_cleanupradius.setRange(0, 9999)
        self.spin_cleanupradius.setValue(200)
        event_layout.addWidget(QLabel("cleanupradius:"), row, 4)
        event_layout.addWidget(self.spin_cleanupradius, row, 5)
        
        row += 1
        self.chk_deletable = QCheckBox("deletable")
        event_layout.addWidget(self.chk_deletable, row, 0)
        
        self.chk_init_random = QCheckBox("init_random")
        event_layout.addWidget(self.chk_init_random, row, 1)
        
        self.chk_remove_damaged = QCheckBox("remove_damaged")
        self.chk_remove_damaged.setChecked(True)
        event_layout.addWidget(self.chk_remove_damaged, row, 2)
        
        row += 1
        self.cmb_position = QComboBox()
        self.cmb_position.addItems(["fixed", "player"])
        event_layout.addWidget(QLabel("position:"), row, 0)
        event_layout.addWidget(self.cmb_position, row, 1)
        
        self.cmb_limit = QComboBox()
        self.cmb_limit.addItems(["mixed", "child", "custom"])
        event_layout.addWidget(QLabel("limit:"), row, 2)
        event_layout.addWidget(self.cmb_limit, row, 3)
        
        self.chk_active = QCheckBox("active")
        self.chk_active.setChecked(True)
        event_layout.addWidget(self.chk_active, row, 4)
        
        layout.addWidget(event_group)
        
        # Zone config group
        zone_group = QGroupBox(tr("vehicle_manager.zone_config"))
        zone_layout = QGridLayout(zone_group)
        
        self.spin_zone_smin = QSpinBox()
        self.spin_zone_smin.setRange(0, 100)
        self.spin_zone_smin.setValue(1)
        zone_layout.addWidget(QLabel("smin:"), 0, 0)
        zone_layout.addWidget(self.spin_zone_smin, 0, 1)
        
        self.spin_zone_smax = QSpinBox()
        self.spin_zone_smax.setRange(0, 100)
        self.spin_zone_smax.setValue(3)
        zone_layout.addWidget(QLabel("smax:"), 0, 2)
        zone_layout.addWidget(self.spin_zone_smax, 0, 3)
        
        self.spin_zone_dmin = QSpinBox()
        self.spin_zone_dmin.setRange(0, 100)
        self.spin_zone_dmin.setValue(3)
        zone_layout.addWidget(QLabel("dmin:"), 0, 4)
        zone_layout.addWidget(self.spin_zone_dmin, 0, 5)
        
        self.spin_zone_dmax = QSpinBox()
        self.spin_zone_dmax.setRange(0, 100)
        self.spin_zone_dmax.setValue(5)
        zone_layout.addWidget(QLabel("dmax:"), 1, 0)
        zone_layout.addWidget(self.spin_zone_dmax, 1, 1)
        
        self.spin_zone_r = QSpinBox()
        self.spin_zone_r.setRange(0, 1000)
        self.spin_zone_r.setValue(45)
        zone_layout.addWidget(QLabel("r:"), 1, 2)
        zone_layout.addWidget(self.spin_zone_r, 1, 3)
        
        layout.addWidget(zone_group)
        
        # Apply button
        btn_apply = QPushButton(tr("vehicle_manager.apply_basic"))
        btn_apply.clicked.connect(self._apply_basic_changes)
        layout.addWidget(btn_apply)
        
        layout.addStretch()
        scroll.setWidget(widget)
        return scroll
    
    def _create_variants_tab(self) -> QWidget:
        """Create variants management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_add_variant = IconButton("plus", tr("vehicle_manager.add_variant"), size=14)
        self.btn_add_variant.clicked.connect(self._add_variant)
        toolbar.addWidget(self.btn_add_variant)
        
        self.btn_clone_variant = IconButton("copy", tr("vehicle_manager.clone_variant"), size=14)
        self.btn_clone_variant.clicked.connect(self._clone_variant)
        toolbar.addWidget(self.btn_clone_variant)
        
        self.btn_delete_variant = IconButton("trash", tr("vehicle_manager.delete_variant"), size=14)
        self.btn_delete_variant.clicked.connect(self._delete_variant)
        toolbar.addWidget(self.btn_delete_variant)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Variants table
        self.tbl_variants = QTableWidget()
        self.tbl_variants.setColumnCount(6)
        self.tbl_variants.setHorizontalHeaderLabels([
            tr("vehicle_manager.classname"),
            tr("vehicle_manager.description"),
            "min", "max", "lootmin", "lootmax"
        ])
        self.tbl_variants.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_variants.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_variants.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_variants.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_variants.setAlternatingRowColors(True)
        self.tbl_variants.cellChanged.connect(self._on_variant_cell_changed)
        
        layout.addWidget(self.tbl_variants)
        
        return widget
    
    def _create_parts_tab(self) -> QWidget:
        """Create parts management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Variant selector
        variant_selector = QHBoxLayout()
        variant_selector.addWidget(QLabel(tr("vehicle_manager.select_variant")))
        
        self.cmb_part_variant = QComboBox()
        self.cmb_part_variant.currentIndexChanged.connect(self._on_part_variant_changed)
        variant_selector.addWidget(self.cmb_part_variant, stretch=1)
        
        layout.addLayout(variant_selector)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_add_part = IconButton("plus", tr("vehicle_manager.add_part"), size=14)
        self.btn_add_part.clicked.connect(self._add_part)
        toolbar.addWidget(self.btn_add_part)
        
        self.btn_delete_part = IconButton("trash", tr("vehicle_manager.delete_part"), size=14)
        self.btn_delete_part.clicked.connect(self._delete_part)
        toolbar.addWidget(self.btn_delete_part)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Parts table
        self.tbl_parts = QTableWidget()
        self.tbl_parts.setColumnCount(5)
        self.tbl_parts.setHorizontalHeaderLabels([
            tr("vehicle_manager.classname"),
            tr("vehicle_manager.label"),
            tr("vehicle_manager.description"),
            tr("vehicle_manager.chance"),
            tr("vehicle_manager.attachment_chance"),
        ])
        self.tbl_parts.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_parts.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_parts.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_parts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_parts.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl_parts.setAlternatingRowColors(True)
        self.tbl_parts.cellChanged.connect(self._on_part_cell_changed)
        
        layout.addWidget(self.tbl_parts)
        
        return widget
    
    def _create_spawns_tab(self) -> QWidget:
        """Create spawn positions management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_add_spawn = IconButton("plus", tr("vehicle_manager.add_spawn"), size=14)
        self.btn_add_spawn.clicked.connect(self._add_spawn)
        toolbar.addWidget(self.btn_add_spawn)
        
        self.btn_borrow_spawn = IconButton("copy", tr("vehicle_manager.borrow_spawn"), size=14)
        self.btn_borrow_spawn.clicked.connect(self._borrow_spawn)
        self.btn_borrow_spawn.setToolTip(tr("vehicle_manager.borrow_spawn_tooltip"))
        toolbar.addWidget(self.btn_borrow_spawn)
        
        self.btn_delete_spawn = IconButton("trash", tr("vehicle_manager.delete_spawn"), size=14)
        self.btn_delete_spawn.clicked.connect(self._delete_spawn)
        toolbar.addWidget(self.btn_delete_spawn)
        
        self.btn_return_borrowed = IconButton("undo", tr("vehicle_manager.return_borrowed"), size=14)
        self.btn_return_borrowed.clicked.connect(self._return_borrowed_spawns)
        self.btn_return_borrowed.setToolTip(tr("vehicle_manager.return_borrowed_tooltip"))
        toolbar.addWidget(self.btn_return_borrowed)
        
        toolbar.addStretch()
        
        # Show count
        self.lbl_spawn_count = QLabel()
        toolbar.addWidget(self.lbl_spawn_count)
        
        layout.addLayout(toolbar)
        
        # Spawns table
        self.tbl_spawns = QTableWidget()
        self.tbl_spawns.setColumnCount(6)
        self.tbl_spawns.setHorizontalHeaderLabels([
            "x", "y", "z", "a (angle)", 
            tr("vehicle_manager.borrowed_from"),
            tr("vehicle_manager.is_custom"),
        ])
        self.tbl_spawns.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_spawns.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl_spawns.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_spawns.setAlternatingRowColors(True)
        self.tbl_spawns.cellChanged.connect(self._on_spawn_cell_changed)
        
        layout.addWidget(self.tbl_spawns)
        
        return widget
    
    def _create_wheels_tab(self) -> QWidget:
        """Create wheel config tab (types.xml)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_add_wheel = IconButton("plus", tr("vehicle_manager.add_wheel_config"), size=14)
        self.btn_add_wheel.clicked.connect(self._add_wheel_config)
        toolbar.addWidget(self.btn_add_wheel)
        
        self.btn_delete_wheel = IconButton("trash", tr("vehicle_manager.delete_wheel_config"), size=14)
        self.btn_delete_wheel.clicked.connect(self._delete_wheel_config)
        toolbar.addWidget(self.btn_delete_wheel)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Wheel configs list
        self.list_wheels = QListWidget()
        self.list_wheels.itemClicked.connect(self._on_wheel_selected)
        layout.addWidget(self.list_wheels, stretch=1)
        
        # Wheel config details
        wheel_details = QGroupBox(tr("vehicle_manager.wheel_details"))
        wheel_layout = QFormLayout(wheel_details)
        
        self.txt_wheel_classname = QLineEdit()
        wheel_layout.addRow(tr("vehicle_manager.classname"), self.txt_wheel_classname)
        
        self.spin_wheel_nominal = QSpinBox()
        self.spin_wheel_nominal.setRange(0, 999)
        self.spin_wheel_nominal.setValue(40)
        wheel_layout.addRow("nominal:", self.spin_wheel_nominal)
        
        self.spin_wheel_min = QSpinBox()
        self.spin_wheel_min.setRange(0, 999)
        self.spin_wheel_min.setValue(30)
        wheel_layout.addRow("min:", self.spin_wheel_min)
        
        self.spin_wheel_lifetime = QSpinBox()
        self.spin_wheel_lifetime.setRange(0, 999999)
        self.spin_wheel_lifetime.setValue(28800)
        wheel_layout.addRow("lifetime:", self.spin_wheel_lifetime)
        
        self.txt_wheel_category = QLineEdit()
        self.txt_wheel_category.setText("lootdispatch")
        wheel_layout.addRow(tr("vehicle_manager.category"), self.txt_wheel_category)
        
        self.txt_wheel_tags = QLineEdit()
        self.txt_wheel_tags.setPlaceholderText("floor, shelves (comma separated)")
        wheel_layout.addRow(tr("vehicle_manager.tags"), self.txt_wheel_tags)
        
        self.txt_wheel_usages = QLineEdit()
        self.txt_wheel_usages.setPlaceholderText("Industrial, Village (comma separated)")
        wheel_layout.addRow(tr("vehicle_manager.usages"), self.txt_wheel_usages)
        
        btn_apply_wheel = QPushButton(tr("vehicle_manager.apply_wheel"))
        btn_apply_wheel.clicked.connect(self._apply_wheel_changes)
        wheel_layout.addRow(btn_apply_wheel)
        
        layout.addWidget(wheel_details)
        
        return widget
    
    def _create_preview_tab(self) -> QWidget:
        """Create XML preview tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Preview selector
        selector = QHBoxLayout()
        selector.addWidget(QLabel(tr("vehicle_manager.preview_file")))
        
        self.cmb_preview_file = QComboBox()
        self.cmb_preview_file.addItems([
            "events.xml",
            "cfgeventspawns.xml", 
            "cfgspawnabletypes.xml",
            "types.xml"
        ])
        self.cmb_preview_file.currentIndexChanged.connect(self._update_preview)
        selector.addWidget(self.cmb_preview_file, stretch=1)
        
        btn_refresh = IconButton("refresh", "", size=14, icon_only=True)
        btn_refresh.clicked.connect(self._update_preview)
        selector.addWidget(btn_refresh)
        
        layout.addLayout(selector)
        
        # Preview text
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFont(QFont("Consolas", 10))
        layout.addWidget(self.txt_preview)
        
        return widget
    
    def _create_footer(self, layout: QVBoxLayout):
        """Create footer with action buttons."""
        footer = QHBoxLayout()
        
        # Summary label
        self.lbl_summary = QLabel()
        footer.addWidget(self.lbl_summary)
        
        footer.addStretch()
        
        # Save & Apply button
        self.btn_save = IconButton("save", tr("vehicle_manager.save_apply"), size=16)
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._save_and_apply)
        footer.addWidget(self.btn_save)
        
        # Close button
        self.btn_close = QPushButton(tr("common.close"))
        self.btn_close.clicked.connect(self.reject)
        footer.addWidget(self.btn_close)
        
        layout.addLayout(footer)
    
    # ==========================================================================
    # DATA LOADING / REFRESH
    # ==========================================================================
    
    def _refresh_vehicle_lists(self):
        """Refresh vehicle lists from data store."""
        self.list_vanilla.clear()
        self.list_modded.clear()
        
        for vehicle in self.vehicle_manager.get_vanilla_vehicles():
            item = QListWidgetItem(vehicle.classname or vehicle.event_name)
            item.setData(Qt.UserRole, vehicle.id)
            if vehicle.description:
                item.setToolTip(vehicle.description)
            self.list_vanilla.addItem(item)
        
        for vehicle in self.vehicle_manager.get_modded_vehicles():
            item = QListWidgetItem(vehicle.classname or vehicle.event_name)
            item.setData(Qt.UserRole, vehicle.id)
            if vehicle.description:
                item.setToolTip(vehicle.description)
            if vehicle.mod_name:
                item.setText(f"{vehicle.classname} ({vehicle.mod_name})")
            self.list_modded.addItem(item)
        
        self._update_summary()
    
    def _update_summary(self):
        """Update summary label."""
        vanilla_count = len(self.vehicle_manager.get_vanilla_vehicles())
        modded_count = len(self.vehicle_manager.get_modded_vehicles())
        self.lbl_summary.setText(
            f"{tr('vehicle_manager.total_vehicles')}: {vanilla_count + modded_count} "
            f"({vanilla_count} {tr('vehicle_manager.vanilla')}, "
            f"{modded_count} {tr('vehicle_manager.modded')})"
        )
    
    def _load_vehicle_details(self, vehicle: VehicleModel):
        """Load vehicle details into UI."""
        self._selected_vehicle = vehicle
        self.lbl_vehicle_name.setText(f"<b>{vehicle.classname or vehicle.event_name}</b>")
        
        # Basic info
        self.txt_classname.setText(vehicle.classname)
        self.txt_event_name.setText(vehicle.event_name)
        self.txt_description.setText(vehicle.description)
        self.txt_mod_name.setText(vehicle.mod_name or "")
        
        idx = self.cmb_category.findData(vehicle.category.value)
        if idx >= 0:
            self.cmb_category.setCurrentIndex(idx)
        
        # Event config
        config = vehicle.event_config
        self.spin_nominal.setValue(config.nominal)
        self.spin_min.setValue(config.min)
        self.spin_max.setValue(config.max)
        self.spin_lifetime.setValue(config.lifetime)
        self.spin_restock.setValue(config.restock)
        self.spin_saferadius.setValue(config.saferadius)
        self.spin_distanceradius.setValue(config.distanceradius)
        self.spin_cleanupradius.setValue(config.cleanupradius)
        self.chk_deletable.setChecked(config.deletable == 1)
        self.chk_init_random.setChecked(config.init_random == 1)
        self.chk_remove_damaged.setChecked(config.remove_damaged == 1)
        self.cmb_position.setCurrentText(config.position)
        self.cmb_limit.setCurrentText(config.limit)
        self.chk_active.setChecked(config.active == 1)
        
        # Zone config
        zone = vehicle.zone_config
        self.spin_zone_smin.setValue(zone.smin)
        self.spin_zone_smax.setValue(zone.smax)
        self.spin_zone_dmin.setValue(zone.dmin)
        self.spin_zone_dmax.setValue(zone.dmax)
        self.spin_zone_r.setValue(zone.r)
        
        # Load variants
        self._load_variants(vehicle)
        
        # Load spawns
        self._load_spawns(vehicle)
        
        # Load wheel configs
        self._load_wheel_configs(vehicle)
        
        # Update preview
        self._update_preview()
        
        # Show details panel
        self.details_stack.setCurrentIndex(1)
    
    def _load_variants(self, vehicle: VehicleModel):
        """Load variants into table."""
        self.tbl_variants.blockSignals(True)
        self.tbl_variants.setRowCount(0)
        
        for variant in vehicle.variants:
            row = self.tbl_variants.rowCount()
            self.tbl_variants.insertRow(row)
            
            self.tbl_variants.setItem(row, 0, QTableWidgetItem(variant.classname))
            self.tbl_variants.setItem(row, 1, QTableWidgetItem(variant.description))
            
            min_item = QTableWidgetItem(str(variant.min_spawn))
            self.tbl_variants.setItem(row, 2, min_item)
            
            max_item = QTableWidgetItem(str(variant.max_spawn))
            self.tbl_variants.setItem(row, 3, max_item)
            
            lootmin_item = QTableWidgetItem(str(variant.loot_min))
            self.tbl_variants.setItem(row, 4, lootmin_item)
            
            lootmax_item = QTableWidgetItem(str(variant.loot_max))
            self.tbl_variants.setItem(row, 5, lootmax_item)
            
            # Store variant ID
            self.tbl_variants.item(row, 0).setData(Qt.UserRole, variant.id)
        
        self.tbl_variants.blockSignals(False)
        
        # Update parts variant combo
        self._update_parts_variant_combo(vehicle)
    
    def _update_parts_variant_combo(self, vehicle: VehicleModel):
        """Update the variant combo box in parts tab."""
        self.cmb_part_variant.blockSignals(True)
        self.cmb_part_variant.clear()
        
        for variant in vehicle.variants:
            self.cmb_part_variant.addItem(variant.classname, variant.id)
        
        self.cmb_part_variant.blockSignals(False)
        
        if self.cmb_part_variant.count() > 0:
            self._on_part_variant_changed(0)
    
    def _load_parts_for_variant(self, variant: VehicleVariant):
        """Load parts for selected variant."""
        self.tbl_parts.blockSignals(True)
        self.tbl_parts.setRowCount(0)
        
        for part in variant.parts:
            row = self.tbl_parts.rowCount()
            self.tbl_parts.insertRow(row)
            
            self.tbl_parts.setItem(row, 0, QTableWidgetItem(part.classname))
            
            # Label combo
            label_combo = QComboBox()
            for label in PartLabel:
                label_combo.addItem(PART_LABEL_NAMES[label], label.value)
            label_combo.setProperty("part_id", part.id)
            label_combo.blockSignals(True)
            idx = label_combo.findData(part.label.value)
            if idx >= 0:
                label_combo.setCurrentIndex(idx)
            label_combo.blockSignals(False)
            label_combo.currentIndexChanged.connect(
                lambda _idx, combo=label_combo, pid=part.id: self._on_part_label_changed(combo, pid)
            )
            self.tbl_parts.setCellWidget(row, 1, label_combo)
            
            self.tbl_parts.setItem(row, 2, QTableWidgetItem(part.description))
            self.tbl_parts.setItem(row, 3, QTableWidgetItem(f"{part.chance:.2f}"))
            self.tbl_parts.setItem(row, 4, QTableWidgetItem(f"{part.attachment_chance:.2f}"))
            
            # Store part ID
            self.tbl_parts.item(row, 0).setData(Qt.UserRole, part.id)
        
        self.tbl_parts.blockSignals(False)

    def _on_part_label_changed(self, combo: QComboBox, part_id: str):
        """Persist label changes from the label combobox into the model."""
        if not self._selected_vehicle:
            return

        variant_id = self.cmb_part_variant.currentData()
        variant: Optional[VehicleVariant] = None
        for v in self._selected_vehicle.variants:
            if v.id == variant_id:
                variant = v
                break
        if not variant:
            return

        part: Optional[VehiclePart] = None
        for p in variant.parts:
            if p.id == part_id:
                part = p
                break
        if not part:
            return

        value = combo.currentData()
        if not value:
            return
        try:
            part.label = PartLabel(value)
        except Exception:
            return
    
    def _load_spawns(self, vehicle: VehicleModel):
        """Load spawn positions into table."""
        self.tbl_spawns.blockSignals(True)
        self.tbl_spawns.setRowCount(0)
        
        for pos in vehicle.spawn_positions:
            row = self.tbl_spawns.rowCount()
            self.tbl_spawns.insertRow(row)
            
            self.tbl_spawns.setItem(row, 0, QTableWidgetItem(f"{pos.x:.6f}"))
            self.tbl_spawns.setItem(row, 1, QTableWidgetItem(f"{pos.y:.2f}" if pos.y else ""))
            self.tbl_spawns.setItem(row, 2, QTableWidgetItem(f"{pos.z:.6f}"))
            self.tbl_spawns.setItem(row, 3, QTableWidgetItem(f"{pos.a:.6f}"))
            self.tbl_spawns.setItem(row, 4, QTableWidgetItem(pos.borrowed_from or ""))
            
            # Custom indicator
            custom_item = QTableWidgetItem("✓" if pos.is_custom else "")
            custom_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_spawns.setItem(row, 5, custom_item)
            
            # Store position ID
            self.tbl_spawns.item(row, 0).setData(Qt.UserRole, pos.id)
            
            # Color borrowed positions differently
            if not pos.is_custom:
                for col in range(6):
                    item = self.tbl_spawns.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 200))
        
        self.tbl_spawns.blockSignals(False)
        self.lbl_spawn_count.setText(f"{tr('vehicle_manager.spawn_count')}: {len(vehicle.spawn_positions)}")
    
    def _load_wheel_configs(self, vehicle: VehicleModel):
        """Load wheel configs into list."""
        self.list_wheels.clear()
        
        for wheel in vehicle.wheel_configs:
            item = QListWidgetItem(wheel.classname)
            item.setData(Qt.UserRole, wheel.id)
            self.list_wheels.addItem(item)
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _on_vehicle_selected(self, item: QListWidgetItem):
        """Handle vehicle selection."""
        vehicle_id = item.data(Qt.UserRole)
        vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
        if vehicle:
            self._load_vehicle_details(vehicle)
    
    def _on_variant_cell_changed(self, row: int, col: int):
        """Handle variant cell change."""
        if not self._selected_vehicle:
            return
        
        if row >= len(self._selected_vehicle.variants):
            return
        
        variant = self._selected_vehicle.variants[row]
        item = self.tbl_variants.item(row, col)
        
        if col == 0:
            variant.classname = item.text()
        elif col == 1:
            variant.description = item.text()
        elif col == 2:
            try:
                variant.min_spawn = int(item.text())
            except ValueError:
                pass
        elif col == 3:
            try:
                variant.max_spawn = int(item.text())
            except ValueError:
                pass
        elif col == 4:
            try:
                variant.loot_min = int(item.text())
            except ValueError:
                pass
        elif col == 5:
            try:
                variant.loot_max = int(item.text())
            except ValueError:
                pass
    
    def _on_part_variant_changed(self, index: int):
        """Handle part variant combo change."""
        if index < 0 or not self._selected_vehicle:
            return
        
        variant_id = self.cmb_part_variant.itemData(index)
        for variant in self._selected_vehicle.variants:
            if variant.id == variant_id:
                self._load_parts_for_variant(variant)
                break
    
    def _on_part_cell_changed(self, row: int, col: int):
        """Handle part cell change."""
        if not self._selected_vehicle:
            return
        
        variant_id = self.cmb_part_variant.currentData()
        variant = None
        for v in self._selected_vehicle.variants:
            if v.id == variant_id:
                variant = v
                break
        
        if not variant or row >= len(variant.parts):
            return
        
        part = variant.parts[row]
        item = self.tbl_parts.item(row, col)
        
        if col == 0:
            part.classname = item.text()
        elif col == 2:
            part.description = item.text()
        elif col == 3:
            try:
                part.chance = float(item.text())
            except ValueError:
                pass
        elif col == 4:
            try:
                part.attachment_chance = float(item.text())
            except ValueError:
                pass
    
    def _on_spawn_cell_changed(self, row: int, col: int):
        """Handle spawn cell change."""
        if not self._selected_vehicle:
            return
        
        if row >= len(self._selected_vehicle.spawn_positions):
            return
        
        pos = self._selected_vehicle.spawn_positions[row]
        item = self.tbl_spawns.item(row, col)
        
        try:
            if col == 0:
                pos.x = float(item.text())
            elif col == 1:
                pos.y = float(item.text()) if item.text() else None
            elif col == 2:
                pos.z = float(item.text())
            elif col == 3:
                pos.a = float(item.text())
        except ValueError:
            pass

        # If the user edits a borrowed spawn, treat it as customized so it won't
        # be removed by "Return borrowed".
        if (not pos.is_custom) and col in (0, 1, 2, 3):
            pos.is_custom = True
            # Update UI indicator for this row
            custom_item = self.tbl_spawns.item(row, 5)
            if custom_item:
                custom_item.setText("✓")
            # Clear borrowed highlight
            for c in range(6):
                it = self.tbl_spawns.item(row, c)
                if it:
                    it.setBackground(QColor())
    
    def _on_wheel_selected(self, item: QListWidgetItem):
        """Handle wheel config selection."""
        if not self._selected_vehicle:
            return
        
        wheel_id = item.data(Qt.UserRole)
        for wheel in self._selected_vehicle.wheel_configs:
            if wheel.id == wheel_id:
                self.txt_wheel_classname.setText(wheel.classname)
                self.spin_wheel_nominal.setValue(wheel.nominal)
                self.spin_wheel_min.setValue(wheel.min)
                self.spin_wheel_lifetime.setValue(wheel.lifetime)
                self.txt_wheel_category.setText(wheel.category)
                self.txt_wheel_tags.setText(", ".join(wheel.tags))
                self.txt_wheel_usages.setText(", ".join(wheel.usages))
                break
    
    # ==========================================================================
    # VEHICLE CRUD ACTIONS
    # ==========================================================================
    
    def _add_vehicle(self):
        """Add a new vehicle."""
        dialog = AddVehicleDialog(self.server_path, self)
        if dialog.exec() == QDialog.Accepted:
            vehicle = dialog.get_vehicle()
            if vehicle:
                if self.vehicle_manager.add_vehicle(vehicle):
                    self._refresh_vehicle_lists()
                    QMessageBox.information(
                        self, tr("common.success"),
                        tr("vehicle_manager.vehicle_added")
                    )
                else:
                    QMessageBox.warning(
                        self, tr("common.warning"),
                        tr("vehicle_manager.vehicle_exists")
                    )
    
    def _delete_selected_vehicle(self):
        """Delete the selected vehicle."""
        if not self._selected_vehicle:
            return
        
        result = QMessageBox.question(
            self, tr("common.confirm"),
            tr("vehicle_manager.confirm_delete", name=self._selected_vehicle.classname),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            if self.vehicle_manager.delete_vehicle(self._selected_vehicle.id):
                self._selected_vehicle = None
                self.details_stack.setCurrentIndex(0)
                self._refresh_vehicle_lists()
    
    def _show_vehicle_context_menu(self, pos):
        """Show context menu for vehicle list."""
        list_widget = self.sender()
        item = list_widget.itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self)
        
        action_edit = menu.addAction(tr("common.edit"))
        action_delete = menu.addAction(tr("common.delete"))
        menu.addSeparator()
        action_export = menu.addAction(tr("vehicle_manager.export_single"))
        
        action = menu.exec_(list_widget.mapToGlobal(pos))
        
        if action == action_edit:
            self._on_vehicle_selected(item)
        elif action == action_delete:
            vehicle_id = item.data(Qt.UserRole)
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if vehicle:
                self._selected_vehicle = vehicle
                self._delete_selected_vehicle()
        elif action == action_export:
            vehicle_id = item.data(Qt.UserRole)
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if vehicle:
                self._selected_vehicle = vehicle
                self._export_single_vehicle()
    
    # ==========================================================================
    # VARIANT ACTIONS
    # ==========================================================================
    
    def _add_variant(self):
        """Add a new variant."""
        if not self._selected_vehicle:
            return
        
        variant = VehicleVariant(
            classname=f"{self._selected_vehicle.classname}_New",
            description="New variant",
        )
        self._selected_vehicle.variants.append(variant)
        self._load_variants(self._selected_vehicle)
    
    def _clone_variant(self):
        """Clone selected variant."""
        if not self._selected_vehicle:
            return
        
        row = self.tbl_variants.currentRow()
        if row < 0 or row >= len(self._selected_vehicle.variants):
            return
        
        original = self._selected_vehicle.variants[row]
        clone = original.clone()
        clone.classname = f"{original.classname}_Copy"
        clone.description = f"Copy of {original.description}"
        
        self._selected_vehicle.variants.append(clone)
        self._load_variants(self._selected_vehicle)
    
    def _delete_variant(self):
        """Delete selected variant."""
        if not self._selected_vehicle:
            return
        
        row = self.tbl_variants.currentRow()
        if row < 0 or row >= len(self._selected_vehicle.variants):
            return
        
        del self._selected_vehicle.variants[row]
        self._load_variants(self._selected_vehicle)
    
    # ==========================================================================
    # PART ACTIONS
    # ==========================================================================
    
    def _add_part(self):
        """Add a new part to selected variant."""
        if not self._selected_vehicle:
            return
        
        variant_id = self.cmb_part_variant.currentData()
        for variant in self._selected_vehicle.variants:
            if variant.id == variant_id:
                part = VehiclePart(
                    classname="NewPart",
                    chance=1.0,
                    attachment_chance=1.0,
                )
                variant.parts.append(part)
                self._load_parts_for_variant(variant)
                break
    
    def _delete_part(self):
        """Delete selected part."""
        if not self._selected_vehicle:
            return
        
        variant_id = self.cmb_part_variant.currentData()
        row = self.tbl_parts.currentRow()
        
        for variant in self._selected_vehicle.variants:
            if variant.id == variant_id:
                if 0 <= row < len(variant.parts):
                    del variant.parts[row]
                    self._load_parts_for_variant(variant)
                break
    
    # ==========================================================================
    # SPAWN ACTIONS
    # ==========================================================================
    
    def _add_spawn(self):
        """Add a new spawn position."""
        if not self._selected_vehicle:
            return
        
        pos = SpawnPosition(
            x=0.0,
            z=0.0,
            a=0.0,
            is_custom=True,
        )
        self._selected_vehicle.spawn_positions.append(pos)
        self._load_spawns(self._selected_vehicle)
    
    def _borrow_spawn(self):
        """Borrow spawn positions from vanilla vehicle."""
        if not self._selected_vehicle:
            return
        
        dialog = BorrowSpawnDialog(self.vehicle_manager, self._selected_vehicle, self)
        if dialog.exec() == QDialog.Accepted:
            self._load_spawns(self._selected_vehicle)
    
    def _delete_spawn(self):
        """Delete selected spawn positions."""
        if not self._selected_vehicle:
            return
        
        rows = set(item.row() for item in self.tbl_spawns.selectedItems())
        
        # Only delete custom spawns
        to_remove = []
        for row in sorted(rows, reverse=True):
            if row < len(self._selected_vehicle.spawn_positions):
                pos = self._selected_vehicle.spawn_positions[row]
                if pos.is_custom:
                    to_remove.append(row)
                else:
                    QMessageBox.warning(
                        self, tr("common.warning"),
                        tr("vehicle_manager.cannot_delete_borrowed")
                    )
        
        for row in to_remove:
            del self._selected_vehicle.spawn_positions[row]
        
        self._load_spawns(self._selected_vehicle)
    
    def _return_borrowed_spawns(self):
        """Return all borrowed spawn positions."""
        if not self._selected_vehicle:
            return
        
        count = self.vehicle_manager.return_borrowed_positions(self._selected_vehicle)
        if count > 0:
            self._load_spawns(self._selected_vehicle)
            QMessageBox.information(
                self, tr("common.success"),
                tr("vehicle_manager.borrowed_returned", count=count)
            )
    
    # ==========================================================================
    # WHEEL CONFIG ACTIONS
    # ==========================================================================
    
    def _add_wheel_config(self):
        """Add a new wheel config."""
        if not self._selected_vehicle:
            return
        
        wheel = WheelTypeConfig(
            classname=f"{self._selected_vehicle.classname}_Wheel",
        )
        self._selected_vehicle.wheel_configs.append(wheel)
        self._load_wheel_configs(self._selected_vehicle)
    
    def _delete_wheel_config(self):
        """Delete selected wheel config."""
        if not self._selected_vehicle:
            return
        
        item = self.list_wheels.currentItem()
        if not item:
            return
        
        wheel_id = item.data(Qt.UserRole)
        self._selected_vehicle.wheel_configs = [
            w for w in self._selected_vehicle.wheel_configs if w.id != wheel_id
        ]
        self._load_wheel_configs(self._selected_vehicle)
    
    def _apply_wheel_changes(self):
        """Apply wheel config changes."""
        if not self._selected_vehicle:
            return
        
        item = self.list_wheels.currentItem()
        if not item:
            return
        
        wheel_id = item.data(Qt.UserRole)
        for wheel in self._selected_vehicle.wheel_configs:
            if wheel.id == wheel_id:
                wheel.classname = self.txt_wheel_classname.text()
                wheel.nominal = self.spin_wheel_nominal.value()
                wheel.min = self.spin_wheel_min.value()
                wheel.lifetime = self.spin_wheel_lifetime.value()
                wheel.category = self.txt_wheel_category.text()
                wheel.tags = [t.strip() for t in self.txt_wheel_tags.text().split(",") if t.strip()]
                wheel.usages = [u.strip() for u in self.txt_wheel_usages.text().split(",") if u.strip()]
                break
        
        self._load_wheel_configs(self._selected_vehicle)
    
    # ==========================================================================
    # APPLY / SAVE ACTIONS
    # ==========================================================================
    
    def _apply_basic_changes(self):
        """Apply basic info and event config changes."""
        if not self._selected_vehicle:
            return
        
        # Update basic info
        self._selected_vehicle.classname = self.txt_classname.text()
        self._selected_vehicle.event_name = self.txt_event_name.text()
        self._selected_vehicle.description = self.txt_description.text()
        self._selected_vehicle.mod_name = self.txt_mod_name.text() or None
        self._selected_vehicle.category = VehicleCategory(self.cmb_category.currentData())
        
        # Update event config
        config = self._selected_vehicle.event_config
        config.nominal = self.spin_nominal.value()
        config.min = self.spin_min.value()
        config.max = self.spin_max.value()
        config.lifetime = self.spin_lifetime.value()
        config.restock = self.spin_restock.value()
        config.saferadius = self.spin_saferadius.value()
        config.distanceradius = self.spin_distanceradius.value()
        config.cleanupradius = self.spin_cleanupradius.value()
        config.deletable = 1 if self.chk_deletable.isChecked() else 0
        config.init_random = 1 if self.chk_init_random.isChecked() else 0
        config.remove_damaged = 1 if self.chk_remove_damaged.isChecked() else 0
        config.position = self.cmb_position.currentText()
        config.limit = self.cmb_limit.currentText()
        config.active = 1 if self.chk_active.isChecked() else 0
        
        # Update zone config
        zone = self._selected_vehicle.zone_config
        zone.smin = self.spin_zone_smin.value()
        zone.smax = self.spin_zone_smax.value()
        zone.dmin = self.spin_zone_dmin.value()
        zone.dmax = self.spin_zone_dmax.value()
        zone.r = self.spin_zone_r.value()
        
        self._refresh_vehicle_lists()
        self._update_preview()
    
    def _update_preview(self):
        """Update XML preview."""
        if not self._selected_vehicle:
            self.txt_preview.clear()
            return
        
        file_type = self.cmb_preview_file.currentText()
        vehicles = [self._selected_vehicle]
        
        if file_type == "events.xml":
            xml = self.vehicle_manager.generate_events_xml(vehicles)
        elif file_type == "cfgeventspawns.xml":
            xml = self.vehicle_manager.generate_event_spawns_xml(vehicles)
        elif file_type == "cfgspawnabletypes.xml":
            xml = self.vehicle_manager.generate_spawnable_types_xml(vehicles)
        elif file_type == "types.xml":
            xml = self.vehicle_manager.generate_types_xml(vehicles)
        else:
            xml = ""
        
        self.txt_preview.setText(xml)
    
    def _save_and_apply(self):
        """Save vehicle data and apply to config files."""
        # Save data store
        if not self.vehicle_manager.save_data():
            QMessageBox.critical(
                self, tr("common.error"),
                tr("vehicle_manager.save_failed")
            )
            return
        
        # Ask which vehicles to apply
        result = QMessageBox.question(
            self, tr("vehicle_manager.apply_configs"),
            tr("vehicle_manager.apply_configs_confirm"),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if result == QMessageBox.Cancel:
            return
        
        if result == QMessageBox.Yes:
            # Apply all modded vehicles
            vehicles = self.vehicle_manager.get_modded_vehicles()
            if vehicles:
                results = self.vehicle_manager.apply_all(vehicles, backup=True)
                
                success = [f for f, ok in results.items() if ok]
                failed = [f for f, ok in results.items() if not ok]
                
                msg = tr("vehicle_manager.apply_results") + "\n\n"
                if success:
                    msg += f"✓ {', '.join(success)}\n"
                if failed:
                    msg += f"✗ {', '.join(failed)}\n"
                
                QMessageBox.information(self, tr("common.success"), msg)
        
        self.vehicles_changed.emit()
    
    # ==========================================================================
    # IMPORT / EXPORT
    # ==========================================================================
    
    def _scan_existing_vehicles(self):
        """Scan mission files for existing vehicles."""
        vehicles = self.vehicle_manager.scan_existing_vehicles()
        
        if not vehicles:
            QMessageBox.information(
                self, tr("common.info"),
                tr("vehicle_manager.no_vehicles_found")
            )
            return
        
        result = QMessageBox.question(
            self, tr("vehicle_manager.scan_found"),
            tr("vehicle_manager.scan_found_count", count=len(vehicles)),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            imported = self.vehicle_manager.import_vehicles_from_scan(vehicles)
            self._refresh_vehicle_lists()
            QMessageBox.information(
                self, tr("common.success"),
                tr("vehicle_manager.imported_count", count=imported)
            )
    
    def _import_vehicles(self):
        """Import vehicles from JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, tr("vehicle_manager.import_title"),
            "", "JSON Files (*.json)"
        )
        
        if filepath:
            count = self.vehicle_manager.import_all_vehicles(Path(filepath))
            self._refresh_vehicle_lists()
            QMessageBox.information(
                self, tr("common.success"),
                tr("vehicle_manager.imported_count", count=count)
            )
    
    def _export_vehicles(self):
        """Export all vehicles to JSON file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, tr("vehicle_manager.export_title"),
            "vehicles_export.json", "JSON Files (*.json)"
        )
        
        if filepath:
            if self.vehicle_manager.export_all_vehicles(Path(filepath)):
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("vehicle_manager.exported_success")
                )
            else:
                QMessageBox.critical(
                    self, tr("common.error"),
                    tr("vehicle_manager.export_failed")
                )
    
    def _export_single_vehicle(self):
        """Export selected vehicle to JSON file."""
        if not self._selected_vehicle:
            return
        
        default_name = f"{self._selected_vehicle.classname}_export.json"
        filepath, _ = QFileDialog.getSaveFileName(
            self, tr("vehicle_manager.export_title"),
            default_name, "JSON Files (*.json)"
        )
        
        if filepath:
            if self.vehicle_manager.export_vehicle(self._selected_vehicle.id, Path(filepath)):
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("vehicle_manager.exported_success")
                )
            else:
                QMessageBox.critical(
                    self, tr("common.error"),
                    tr("vehicle_manager.export_failed")
                )


# ==============================================================================
# ADD VEHICLE DIALOG
# ==============================================================================

class AddVehicleDialog(QDialog):
    """Dialog for adding a new vehicle."""
    
    def __init__(self, server_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.server_path = server_path
        self._vehicle: Optional[VehicleModel] = None
        
        self.setWindowTitle(tr("vehicle_manager.add_vehicle"))
        self.setMinimumWidth(500)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        
        # Info group
        info_group = QGroupBox(tr("vehicle_manager.basic_info"))
        info_layout = QFormLayout(info_group)
        
        self.txt_classname = QLineEdit()
        self.txt_classname.setPlaceholderText("e.g., Hatchback_02 or MBM_SuzukiGSXR750")
        info_layout.addRow(tr("vehicle_manager.classname"), self.txt_classname)
        
        self.txt_event_name = QLineEdit()
        self.txt_event_name.setPlaceholderText("e.g., VehicleHatchback02")
        info_layout.addRow(tr("vehicle_manager.event_name"), self.txt_event_name)
        
        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText(tr("vehicle_manager.description_hint"))
        info_layout.addRow(tr("vehicle_manager.description"), self.txt_description)
        
        self.cmb_category = QComboBox()
        self.cmb_category.addItem(tr("vehicle_manager.category_modded"), VehicleCategory.MODDED.value)
        self.cmb_category.addItem(tr("vehicle_manager.category_vanilla"), VehicleCategory.VANILLA.value)
        info_layout.addRow(tr("vehicle_manager.category"), self.cmb_category)
        
        self.txt_mod_name = QLineEdit()
        self.txt_mod_name.setPlaceholderText(tr("vehicle_manager.mod_name_hint"))
        info_layout.addRow(tr("vehicle_manager.mod_name"), self.txt_mod_name)
        
        layout.addWidget(info_group)
        
        # Auto-generate event name
        self.txt_classname.textChanged.connect(self._auto_generate_event_name)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _auto_generate_event_name(self, text: str):
        """Auto-generate event name from classname."""
        if text:
            # Remove underscores and capitalize
            event_name = "Vehicle" + text.replace("_", "")
            self.txt_event_name.setText(event_name)
    
    def _accept(self):
        """Accept and create vehicle."""
        classname = self.txt_classname.text().strip()
        event_name = self.txt_event_name.text().strip()
        
        if not classname or not event_name:
            QMessageBox.warning(
                self, tr("common.warning"),
                tr("vehicle_manager.required_fields")
            )
            return
        
        self._vehicle = VehicleModel(
            classname=classname,
            event_name=event_name,
            description=self.txt_description.text().strip(),
            category=VehicleCategory(self.cmb_category.currentData()),
            mod_name=self.txt_mod_name.text().strip() or None,
        )
        
        # Add default variant
        self._vehicle.variants.append(VehicleVariant(
            classname=classname,
            description="Base variant",
        ))
        
        self.accept()
    
    def get_vehicle(self) -> Optional[VehicleModel]:
        """Get the created vehicle."""
        return self._vehicle


# ==============================================================================
# BORROW SPAWN DIALOG
# ==============================================================================

class BorrowSpawnDialog(QDialog):
    """Dialog for borrowing spawn positions from vanilla vehicles."""
    
    def __init__(self, manager: VehicleManager, target_vehicle: VehicleModel,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.manager = manager
        self.target_vehicle = target_vehicle
        
        self.setWindowTitle(tr("vehicle_manager.borrow_spawn"))
        self.setMinimumSize(600, 500)
        
        self._setup_ui()
        self._load_vanilla_vehicles()
    
    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        
        # Info label
        info = QLabel(tr("vehicle_manager.borrow_info"))
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Vanilla vehicle selector
        selector = QHBoxLayout()
        selector.addWidget(QLabel(tr("vehicle_manager.select_vanilla")))
        
        self.cmb_vanilla = QComboBox()
        self.cmb_vanilla.currentIndexChanged.connect(self._on_vanilla_selected)
        selector.addWidget(self.cmb_vanilla, stretch=1)
        
        layout.addLayout(selector)
        
        # Positions list
        self.list_positions = QListWidget()
        self.list_positions.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.list_positions)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_vanilla_vehicles(self):
        """Load vanilla vehicles into combo."""
        available = self.manager.get_available_vanilla_positions(
            exclude_event=self.target_vehicle.event_name
        )
        
        for event_name in available:
            self.cmb_vanilla.addItem(event_name, event_name)
    
    def _on_vanilla_selected(self, index: int):
        """Handle vanilla vehicle selection."""
        self.list_positions.clear()
        
        if index < 0:
            return
        
        event_name = self.cmb_vanilla.currentData()
        vehicle = self.manager.data_store.get_vehicle_by_event_name(event_name)
        
        if vehicle:
            for pos in vehicle.spawn_positions:
                item = QListWidgetItem(
                    f"x={pos.x:.2f}, z={pos.z:.2f}, a={pos.a:.2f}"
                )
                item.setData(Qt.UserRole, pos.id)
                item.setCheckState(Qt.Unchecked)
                self.list_positions.addItem(item)
    
    def _accept(self):
        """Accept and borrow positions."""
        event_name = self.cmb_vanilla.currentData()
        if not event_name:
            self.reject()
            return
        
        position_ids = []
        for i in range(self.list_positions.count()):
            item = self.list_positions.item(i)
            if item.checkState() == Qt.Checked:
                position_ids.append(item.data(Qt.UserRole))
        
        if position_ids:
            self.manager.borrow_positions_from_vanilla(
                self.target_vehicle, event_name, position_ids
            )
        
        self.accept()
