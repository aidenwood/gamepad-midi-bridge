"""UI primitives — Radix-for-Qt component library.

Each primitive sets its own complete stylesheet at construction time using
design tokens, making it immune to Qt CSS cascade failures caused by
WA_TranslucentBackground on ancestor widgets.

Exports:
    UIButton          — QPushButton with variant + size
    UIChromeFrame     — opaque QFrame for app chrome (translucency-immune)
    ReflowFrame       — QFrame with a zero width floor, for re-arranging bars
    ReflowWidget      — QWidget twin of ReflowFrame
    UIInput           — QLineEdit
    UISpinBox         — QSpinBox
    UIDoubleSpinBox   — QDoubleSpinBox
    UILabel           — QLabel with semantic variants
    ElidingLabel      — QLabel that ellipsises instead of clipping
    UICard            — QFrame card with header/body/footer slots + variant
    UIDropdownMenu    — QMenu wrapper with Radix-style fluent build API
    attach_context_menu — bind a UIDropdownMenu to a widget's right-click
"""

from gamepad_midi_bridge.ui.primitives.button import UIButton
from gamepad_midi_bridge.ui.primitives.card import UICard
from gamepad_midi_bridge.ui.primitives.context_menu import attach_context_menu
from gamepad_midi_bridge.ui.primitives.dropdown import UIDropdownMenu, style_as_dropdown
from gamepad_midi_bridge.ui.primitives.frame import (
    ReflowFrame,
    ReflowWidget,
    UIChromeFrame,
)
from gamepad_midi_bridge.ui.primitives.input import UIDoubleSpinBox, UIInput, UISpinBox
from gamepad_midi_bridge.ui.primitives.label import ElidingLabel, UILabel

__all__ = [
    "ElidingLabel",
    "ReflowFrame",
    "ReflowWidget",
    "UIButton",
    "UICard",
    "UIChromeFrame",
    "UIDoubleSpinBox",
    "UIDropdownMenu",
    "style_as_dropdown",
    "UIInput",
    "UILabel",
    "UISpinBox",
    "attach_context_menu",
]
