"""Sidebar Navigation Widget - Vortex-style sidebar navigation."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame, QListView, QGraphicsDropShadowEffect, QPushButton, QSizePolicy,
    QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient, QPen, QBrush, QIcon
from PySide6.QtWidgets import QStyleOptionViewItem

from src.ui.icons import Icons
from src.ui.theme_manager import ThemeManager


class _SidebarBrandingHeader(QFrame):
    """A custom-painted header that adapts to the current accent/theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = "#0078d4"
        self._dark = True
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_theme(self, accent: str, dark: bool):
        self._accent = accent or "#0078d4"
        self._dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        accent = QColor(self._accent)
        top = QColor(accent)
        bottom = QColor(accent)

        # Make the gradient feel richer without looking neon.
        if self._dark:
            top = QColor(accent).lighter(112)
            bottom = QColor(accent).darker(108)
        else:
            top = QColor(accent).lighter(118)
            bottom = QColor(accent).darker(112)

        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        painter.fillRect(rect, QBrush(grad))

        # Soft "aurora" blobs for depth.
        blob1 = QColor(255, 255, 255, 26 if self._dark else 18)
        blob2 = QColor(0, 0, 0, 28 if self._dark else 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(blob1)
        painter.drawEllipse(QRectF(-40, -60, rect.width() * 1.05, rect.height() * 1.05))
        painter.setBrush(blob2)
        painter.drawEllipse(QRectF(rect.width() * 0.25, rect.height() * 0.15, rect.width() * 0.95, rect.height() * 0.95))

        # Subtle diagonal pattern.
        pattern = QColor(255, 255, 255, 10 if self._dark else 8)
        painter.setPen(QPen(pattern, 1))
        step = 16
        for x in range(-rect.height(), rect.width(), step):
            painter.drawLine(x, rect.height(), x + rect.height(), 0)

        # Bottom divider.
        divider = QColor(0, 0, 0, 80 if self._dark else 55)
        painter.setPen(QPen(divider, 1))
        painter.drawLine(0, rect.height() - 1, rect.width(), rect.height() - 1)

        painter.end()


class _CollapsedIconDelegate(QStyledItemDelegate):
    """Paints a centered Vortex-style tile with a centered icon (collapsed sidebar)."""

    def __init__(
        self,
        parent=None,
        icon_size: int = 22,
        tile_width: int = 56,
        tile_radius: int = 14,
        accent_bar_width: int = 4,
        accent_inset_y: int = 10,
    ):
        super().__init__(parent)
        self._icon_size = int(icon_size)
        self._tile_width = int(tile_width)
        self._tile_radius = int(tile_radius)
        self._accent_bar_width = int(accent_bar_width)
        self._accent_inset_y = int(accent_inset_y)

    def set_icon_size(self, size: int):
        self._icon_size = int(size)

    def set_tile_width(self, width: int):
        self._tile_width = int(width)

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        icon = opt.icon

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Centered tile rect inside the full row rect.
        row = opt.rect
        tile_w = max(0, min(self._tile_width, row.width()))
        tile_x = row.x() + (row.width() - tile_w) // 2
        tile_rect = QRect(tile_x, row.y(), tile_w, row.height())

        hovered = bool(opt.state & QStyle.State_MouseOver)
        selected = bool(opt.state & QStyle.State_Selected)

        # Background (match the previous QSS intent).
        if selected:
            bg = QColor(255, 255, 255, 15)  # ~0.06
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(tile_rect), self._tile_radius, self._tile_radius)
        elif hovered:
            bg = QColor(255, 255, 255, 9)  # ~0.035
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(tile_rect), self._tile_radius, self._tile_radius)

        # Accent bar when selected.
        if selected:
            try:
                accent = QColor(ThemeManager.get_current_accent())
            except Exception:
                accent = QColor("#0078d4")
            accent.setAlpha(220)

            bar_w = max(1, self._accent_bar_width)
            inset_y = max(0, self._accent_inset_y)
            bar_h = max(0, tile_rect.height() - 2 * inset_y)
            bar_x = tile_rect.x() + 2
            bar_y = tile_rect.y() + inset_y
            bar_rect = QRect(bar_x, bar_y, bar_w, bar_h)

            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawRoundedRect(QRectF(bar_rect), 2.0, 2.0)

        if icon.isNull():
            painter.restore()
            return

        size = self._icon_size
        pm = icon.pixmap(size, size)
        x = tile_rect.x() + (tile_rect.width() - size) // 2
        y = tile_rect.y() + (tile_rect.height() - size) // 2
        painter.drawPixmap(x, y, pm)

        painter.restore()


class SidebarWidget(QWidget):
    """Vortex-style sidebar navigation widget."""
    
    item_selected = Signal(int)  # Emits index of selected item
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded_width = 220
        self._collapsed_width = 76
        self.setMinimumWidth(self._expanded_width)
        self.setMaximumWidth(self._expanded_width)
        # Icon size used for sidebar items (width, height)
        # Reverted to original small size for menu icons
        self._sidebar_icon_size = 20
        # Branding/logo sizing is adaptive (based on sidebar width)
        # Expanded: show a prominent logo badge.
        # Collapsed: show a compact icon-only logo.
        self._logo_expanded_min_size = 112
        self._logo_expanded_max_size = 150
        self._logo_collapsed_min_size = 26
        self._logo_collapsed_max_size = 44

        # Collapsed sidebar item sizing
        self._collapsed_item_h = 56
        self._collapsed_item_gap = 6
        self._collapsed_tile_w = 56

        self._collapsed = False
        self.setProperty("collapsed", False)

        self._width_anim_min: QPropertyAnimation | None = None
        self._width_anim_max: QPropertyAnimation | None = None
        self._items = []  # Store item data (icon_name, text)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # App branding header (logo only — no title text)
        self.header = _SidebarBrandingHeader()
        self.header.setObjectName("sidebarHeader")
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(0)
        self._header_layout = header_layout

        self.logo_badge = QFrame()
        self.logo_badge.setObjectName("sidebarLogoBadge")
        badge_layout = QVBoxLayout(self.logo_badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        self._badge_layout = badge_layout

        self.logo_label = QLabel()
        self.logo_label.setObjectName("sidebarLogo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        badge_layout.addWidget(self.logo_label)

        header_layout.addStretch(1)
        header_layout.addWidget(self.logo_badge, alignment=Qt.AlignCenter)
        header_layout.addStretch(1)

        layout.addWidget(self.header)

        self._update_branding_geometry()
        self._apply_branding_effects()

        # Keep the branding updated when the theme changes.
        try:
            ThemeManager.add_observer(self._on_theme_changed)
        except Exception:
            pass
        
        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("sidebar")
        self.nav_list.setSpacing(2)
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        # Remove any implicit frame/margins so IconMode grid can center reliably.
        self.nav_list.setFrameShape(QFrame.NoFrame)
        self.nav_list.setContentsMargins(0, 0, 0, 0)
        self.nav_list.setViewportMargins(0, 0, 0, 0)
        self.nav_list.setVerticalScrollMode(QListView.ScrollPerPixel)
        # Prevent the extra horizontal scrollbar (especially in collapsed IconMode).
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setMouseTracking(True)
        self.nav_list.viewport().setMouseTracking(True)
        # Keep sidebar menu icons at the original small size
        self.nav_list.setIconSize(QSize(self._sidebar_icon_size, self._sidebar_icon_size))
        self.nav_list.currentRowChanged.connect(self._on_row_changed)

        self._default_delegate = self.nav_list.itemDelegate()
        self._collapsed_delegate = _CollapsedIconDelegate(
            self.nav_list,
            icon_size=22,
            tile_width=self._collapsed_tile_w,
            tile_radius=14,
        )
        
        layout.addWidget(self.nav_list, stretch=1)

        # Bottom controls (collapse button + footer)
        bottom = QFrame()
        bottom.setObjectName("sidebarBottom")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(10, 8, 10, 10)
        bottom_layout.setSpacing(6)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setObjectName("sidebarCollapseBtn")
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_collapse.setMinimumHeight(36)
        self.btn_collapse.setIconSize(QSize(18, 18))
        self.btn_collapse.setToolTip("Collapse sidebar")
        self.btn_collapse.clicked.connect(self.toggle_collapsed)
        bottom_layout.addWidget(self.btn_collapse)

        # Ensure correct icon on first paint.
        self._refresh_collapse_button()
        
        self.footer = QLabel()
        self.footer.setStyleSheet("color: #666; font-size: 10px; padding: 8px 16px;")
        self.footer.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self.footer)

        layout.addWidget(bottom)
    
    def add_item(self, icon_name: str, text: str):
        """Add a navigation item with SVG icon."""
        item = QListWidgetItem(text)
        # Keep the original item height for menu items
        item.setSizeHint(QSize(0, 44))

        icon = Icons.get_icon(icon_name, size=self._sidebar_icon_size)
        item.setIcon(icon)
        
        font = QFont()
        font.setPointSize(11)
        item.setFont(font)
        item.setTextAlignment(Qt.AlignVCenter)
        
        self.nav_list.addItem(item)
        self._items.append((icon_name, text))

        # If collapsed, keep new items icon-only too.
        if self._collapsed:
            item.setToolTip(text)
            item.setText("")
            item.setTextAlignment(Qt.AlignCenter)
            # Use full-width rows in collapsed mode so icon can be centered perfectly.
            item.setSizeHint(QSize(max(0, self.nav_list.viewport().width()), self._collapsed_item_h))
            item.setIcon(Icons.get_icon(icon_name, size=22))
    
    def set_current_index(self, index: int):
        """Set the current selected index."""
        self.nav_list.setCurrentRow(index)
    
    def get_current_index(self) -> int:
        """Get current selected index."""
        return self.nav_list.currentRow()
    
    def update_item_text(self, index: int, icon_name: str, text: str):
        """Update text and icon of an item at index."""
        item = self.nav_list.item(index)
        if item:
            if self._collapsed:
                item.setToolTip(text)
                item.setText("")
                item.setTextAlignment(Qt.AlignCenter)
                item.setSizeHint(QSize(max(0, self.nav_list.viewport().width()), self._collapsed_item_h))
                item.setIcon(Icons.get_icon(icon_name, size=22))
            else:
                item.setToolTip("")
                item.setText(text)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setSizeHint(QSize(0, 44))
                item.setIcon(Icons.get_icon(icon_name, size=self._sidebar_icon_size))
            
            # Update stored data
            if index < len(self._items):
                self._items[index] = (icon_name, text)
    
    def refresh_icons(self):
        """Refresh all icons (call after theme change)."""
        size = 22 if self._collapsed else self._sidebar_icon_size
        for i, (icon_name, text) in enumerate(self._items):
            item = self.nav_list.item(i)
            if item:
                icon = Icons.get_icon(icon_name, size=size)
                item.setIcon(icon)

        self._refresh_logo()
        self._apply_branding_effects()

    def _refresh_logo(self):
        try:
            logo_size = self._compute_logo_size()
            self.logo_label.setPixmap(Icons.get_app_logo_pixmap(size=logo_size, variant="auto"))
        except Exception:
            pass

    def _compute_logo_size(self) -> int:
        # Keep the logo comfortably inside the fixed-width sidebar.
        if self._collapsed:
            # 76px wide: target a compact mark (avoid overflow)
            available = max(0, self._collapsed_width - 24)
            size = int(available * 0.78)
            return max(self._logo_collapsed_min_size, min(self._logo_collapsed_max_size, size))

        # Expanded: allow a larger badge
        available = max(0, self.width() - 24)
        size = int(available * 0.78)
        return max(self._logo_expanded_min_size, min(self._logo_expanded_max_size, size))

    def _update_branding_geometry(self):
        """Update logo/badge sizing based on current sidebar width."""
        logo_size = self._compute_logo_size()

        # Tighten padding/margins when collapsed.
        if getattr(self, "_badge_layout", None) is not None:
            pad = 6 if self._collapsed else 10
            self._badge_layout.setContentsMargins(pad, pad, pad, pad)
        if getattr(self, "_header_layout", None) is not None:
            self._header_layout.setContentsMargins(12, 12, 12, 12)

        badge_pad = 12 if self._collapsed else 20
        badge_size = logo_size + badge_pad

        self.logo_label.setFixedSize(logo_size, logo_size)
        self.logo_badge.setFixedSize(badge_size, badge_size)
        self.header.setFixedHeight(badge_size + (24 if self._collapsed else 28))
        self._refresh_logo()

    def _sync_collapsed_grid(self):
        """Keep IconMode grid size in sync with the actual viewport width."""
        if not self._collapsed:
            return
        if self.nav_list.viewMode() != QListView.IconMode:
            return
        try:
            w = int(self.nav_list.viewport().width())
        except Exception:
            w = int(self._collapsed_width)
        self.nav_list.setGridSize(QSize(max(0, w), self._collapsed_item_h))

    def _sync_collapsed_rows(self):
        """Ensure collapsed ListMode rows span the full viewport width."""
        if not self._collapsed:
            return
        if self.nav_list.viewMode() != QListView.ListMode:
            return
        try:
            w = int(self.nav_list.viewport().width())
        except Exception:
            w = int(self._collapsed_width)
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if item is not None:
                item.setSizeHint(QSize(max(0, w), self._collapsed_item_h))

    def _apply_branding_effects(self):
        """Apply a subtle shadow to the logo badge (theme/accent aware)."""
        try:
            accent = ThemeManager.get_current_accent()
        except Exception:
            accent = "#0078d4"

        try:
            self.header.set_theme(accent=accent, dark=ThemeManager.is_dark_theme())
        except Exception:
            pass

        color = QColor(accent)
        color.setAlpha(90 if ThemeManager.is_dark_theme() else 55)

        shadow = QGraphicsDropShadowEffect(self.logo_badge)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 6)
        shadow.setColor(color)
        self.logo_badge.setGraphicsEffect(shadow)

        # btn_collapse is created later in _setup_ui.
        if hasattr(self, "btn_collapse"):
            self._refresh_collapse_button()

    def _refresh_collapse_button(self):
        icon_name = "chevron_right" if self._collapsed else "chevron_left"
        self.btn_collapse.setIcon(Icons.get_icon(icon_name, size=18))

    def _on_theme_changed(self, *_):
        self._refresh_logo()
        self._apply_branding_effects()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed, animate=True)

    def set_collapsed(self, collapsed: bool, animate: bool = True):
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return

        self._collapsed = collapsed
        self.setProperty("collapsed", collapsed)
        self.style().unpolish(self)
        self.style().polish(self)

        # Update list to icon-only mode.
        if collapsed:
            self._collapsed_delegate.set_icon_size(22)
            self._collapsed_delegate.set_tile_width(self._collapsed_tile_w)
            self.nav_list.setItemDelegate(self._collapsed_delegate)
            for i, (icon_name, text) in enumerate(self._items):
                item = self.nav_list.item(i)
                if item:
                    item.setToolTip(text)
                    item.setText("")
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setSizeHint(QSize(max(0, self.nav_list.viewport().width()), self._collapsed_item_h))
                    item.setIcon(Icons.get_icon(icon_name, size=22))

            # Use ListMode rows + delegate centering for pixel-perfect alignment.
            self.nav_list.setViewMode(QListView.ListMode)
            self.nav_list.setSpacing(self._collapsed_item_gap)
            self.nav_list.setIconSize(QSize(22, 22))
            self._sync_collapsed_rows()
            self.footer.setVisible(False)
            self.btn_collapse.setToolTip("Expand sidebar")
            # Apply a narrow, local stylesheet to remove leftover padding
            self.nav_list.setStyleSheet(
                "QListWidget#sidebar { padding: 0px; margin: 0px; outline: none; border: none; }"
            )
        else:
            self.nav_list.setItemDelegate(self._default_delegate)
            for i, (icon_name, text) in enumerate(self._items):
                item = self.nav_list.item(i)
                if item:
                    item.setToolTip("")
                    item.setText(text)
                    item.setTextAlignment(Qt.AlignVCenter)
                    item.setSizeHint(QSize(0, 44))
                    item.setIcon(Icons.get_icon(icon_name, size=self._sidebar_icon_size))

            self.nav_list.setViewMode(QListView.ListMode)
            self.nav_list.setSpacing(2)
            self.nav_list.setIconSize(QSize(self._sidebar_icon_size, self._sidebar_icon_size))
            self.footer.setVisible(True)
            self.btn_collapse.setToolTip("Collapse sidebar")
            # Clear local overrides so global stylesheet takes effect again
            self.nav_list.setStyleSheet("")

        self._update_branding_geometry()
        self._apply_branding_effects()

        target = self._collapsed_width if collapsed else self._expanded_width
        if not animate:
            self.setMinimumWidth(target)
            self.setMaximumWidth(target)
            return

        # Slide animation by animating min/max width together.
        start = int(self.width())
        if self._width_anim_min is not None:
            try:
                self._width_anim_min.stop()
            except Exception:
                pass
        if self._width_anim_max is not None:
            try:
                self._width_anim_max.stop()
            except Exception:
                pass

        self._width_anim_min = QPropertyAnimation(self, b"minimumWidth")
        self._width_anim_max = QPropertyAnimation(self, b"maximumWidth")
        for anim in (self._width_anim_min, self._width_anim_max):
            anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.InOutCubic)
            anim.setStartValue(start)
            anim.setEndValue(target)
            anim.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_branding_geometry()
        self._sync_collapsed_grid()
        self._sync_collapsed_rows()
    
    def set_footer_text(self, text: str):
        """Set footer text (e.g., version info)."""
        self.footer.setText(text)
    
    def _on_row_changed(self, row: int):
        """Handle row selection change."""
        if row >= 0:
            self.item_selected.emit(row)
