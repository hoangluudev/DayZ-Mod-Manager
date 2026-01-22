"""
UI Factories and Builders
Helper functions to create common UI patterns with less boilerplate.
"""

from typing import Optional, Callable, List, Any
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFormLayout,
    QComboBox, QCheckBox, QSpinBox, QLineEdit, QPushButton,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt

from shared.utils.locale_manager import tr
from shared.ui.widgets import SectionBox, IconButton, PathSelector


def create_header_layout(
    title: str,
    buttons: Optional[List[QWidget]] = None,
) -> QHBoxLayout:
    """
    Create a standard header layout with title and action buttons.
    
    Args:
        title: Header title text (can include HTML like <h2>)
        buttons: Optional list of buttons to add on the right
    
    Returns:
        Configured QHBoxLayout
    """
    layout = QHBoxLayout()
    layout.setSpacing(8)
    
    label = QLabel(title)
    layout.addWidget(label)
    layout.addStretch()
    
    if buttons:
        for btn in buttons:
            layout.addWidget(btn)
    
    return layout


def create_form_section(
    title: str,
    fields: List[dict],
    parent: Optional[QWidget] = None,
) -> tuple[SectionBox, dict]:
    """
    Create a form section with labeled fields.
    
    Args:
        title: Section title
        fields: List of field definitions:
            - {"key": "field_name", "label": "Label:", "type": "text|combo|check|spin|path", ...}
        parent: Parent widget
    
    Returns:
        Tuple of (SectionBox, dict of field widgets keyed by field key)
    """
    section = SectionBox(title)
    form = QFormLayout()
    form.setSpacing(12)
    
    widgets = {}
    
    for field in fields:
        key = field["key"]
        label = field.get("label", "")
        field_type = field.get("type", "text")
        
        widget = None
        
        if field_type == "text":
            widget = QLineEdit()
            if "placeholder" in field:
                widget.setPlaceholderText(field["placeholder"])
            if "default" in field:
                widget.setText(str(field["default"]))
                
        elif field_type == "combo":
            widget = QComboBox()
            for item in field.get("items", []):
                if isinstance(item, tuple):
                    widget.addItem(item[0], item[1])
                else:
                    widget.addItem(str(item), item)
                    
        elif field_type == "check":
            widget = QCheckBox(field.get("text", ""))
            if field.get("default"):
                widget.setChecked(True)
                
        elif field_type == "spin":
            widget = QSpinBox()
            widget.setMinimum(field.get("min", 0))
            widget.setMaximum(field.get("max", 100))
            if "default" in field:
                widget.setValue(field["default"])
                
        elif field_type == "path":
            widget = PathSelector(
                path=field.get("default", ""),
                dialog_type=field.get("dialog_type", "folder"),
            )
        
        if widget:
            widgets[key] = widget
            if label:
                form.addRow(label, widget)
            else:
                form.addRow(widget)
            
            # Add description if provided
            if "description" in field:
                desc = QLabel(field["description"])
                desc.setStyleSheet("color: gray; font-size: 11px;")
                form.addRow("", desc)
    
    section.add_layout(form)
    return section, widgets


def create_action_button(
    icon_name: str,
    text: str = "",
    tooltip: str = "",
    size: int = 16,
    icon_only: bool = False,
    on_click: Optional[Callable] = None,
) -> IconButton:
    """
    Create a styled action button with icon.
    
    Args:
        icon_name: Icon name from Icons registry
        text: Button text (optional)
        tooltip: Tooltip text
        size: Icon size
        icon_only: If True, only show icon
        on_click: Click handler
    
    Returns:
        Configured IconButton
    """
    btn = IconButton(
        icon_name=icon_name,
        text=text,
        size=size,
        icon_only=icon_only,
    )
    
    if tooltip:
        btn.setToolTip(tooltip)
    
    if on_click:
        btn.clicked.connect(on_click)
    
    return btn


def create_status_label(
    text: str,
    status: str = "info",  # "success", "warning", "error", "info"
    with_icon: bool = True,
) -> QWidget:
    """
    Create a status label with optional icon.
    
    Args:
        text: Status text
        status: Status type for styling
        with_icon: Whether to include status icon
    
    Returns:
        Widget containing the status label
    """
    from shared.ui.icons import Icons
    
    colors = {
        "success": "#4caf50",
        "warning": "#ff9800",
        "error": "#f44336",
        "info": "#4caf50",
    }
    color = colors.get(status, colors["info"])
    
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    
    if with_icon:
        icon_label = QLabel()
        icon_label.setPixmap(Icons.get_pixmap(status, color=color, size=14))
        layout.addWidget(icon_label)
    
    text_label = QLabel(text)
    text_label.setStyleSheet(f"color: {color}; font-size: 11px;")
    layout.addWidget(text_label)
    layout.addStretch()
    
    return container


def create_button_row(
    buttons: List[dict],
    alignment: str = "right",  # "left", "center", "right"
) -> QHBoxLayout:
    """
    Create a row of buttons.
    
    Args:
        buttons: List of button definitions:
            - {"text": "...", "icon": "...", "primary": bool, "on_click": callable}
        alignment: Button alignment
    
    Returns:
        Configured QHBoxLayout
    """
    layout = QHBoxLayout()
    layout.setSpacing(8)
    
    if alignment in ("center", "right"):
        layout.addStretch()
    
    for btn_def in buttons:
        if "icon" in btn_def:
            btn = IconButton(
                icon_name=btn_def["icon"],
                text=btn_def.get("text", ""),
                size=btn_def.get("size", 16),
            )
        else:
            btn = QPushButton(btn_def.get("text", ""))
        
        if btn_def.get("primary"):
            btn.setStyleSheet("padding: 8px 16px;")
        
        if "tooltip" in btn_def:
            btn.setToolTip(btn_def["tooltip"])
        
        if "on_click" in btn_def:
            btn.clicked.connect(btn_def["on_click"])
        
        layout.addWidget(btn)
    
    if alignment in ("center", "left"):
        layout.addStretch()
    
    return layout


class FormBuilder:
    """
    Builder class for creating forms with fluent API.
    
    Usage:
        form = FormBuilder("Section Title")
        form.add_text("name", "Name:")
        form.add_combo("type", "Type:", [("opt1", "Option 1"), ...])
        form.add_check("enabled", "Enable feature")
        section, widgets = form.build()
    """
    
    def __init__(self, title: str):
        self._title = title
        self._fields: List[dict] = []
    
    def add_text(
        self,
        key: str,
        label: str,
        default: str = "",
        placeholder: str = "",
        description: str = "",
    ) -> "FormBuilder":
        """Add a text field."""
        self._fields.append({
            "key": key,
            "label": label,
            "type": "text",
            "default": default,
            "placeholder": placeholder,
            "description": description,
        })
        return self
    
    def add_combo(
        self,
        key: str,
        label: str,
        items: List,
        description: str = "",
    ) -> "FormBuilder":
        """Add a combo box."""
        self._fields.append({
            "key": key,
            "label": label,
            "type": "combo",
            "items": items,
            "description": description,
        })
        return self
    
    def add_check(
        self,
        key: str,
        text: str,
        default: bool = False,
        description: str = "",
    ) -> "FormBuilder":
        """Add a checkbox."""
        self._fields.append({
            "key": key,
            "label": "",
            "type": "check",
            "text": text,
            "default": default,
            "description": description,
        })
        return self
    
    def add_spin(
        self,
        key: str,
        label: str,
        min_val: int = 0,
        max_val: int = 100,
        default: int = 0,
        description: str = "",
    ) -> "FormBuilder":
        """Add a spin box."""
        self._fields.append({
            "key": key,
            "label": label,
            "type": "spin",
            "min": min_val,
            "max": max_val,
            "default": default,
            "description": description,
        })
        return self
    
    def add_path(
        self,
        key: str,
        label: str,
        default: str = "",
        dialog_type: str = "folder",
        description: str = "",
    ) -> "FormBuilder":
        """Add a path selector."""
        self._fields.append({
            "key": key,
            "label": label,
            "type": "path",
            "default": default,
            "dialog_type": dialog_type,
            "description": description,
        })
        return self
    
    def build(self) -> tuple[SectionBox, dict]:
        """Build the form section."""
        return create_form_section(self._title, self._fields)
