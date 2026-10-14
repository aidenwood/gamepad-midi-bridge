"""UI primitives — Radix-for-Qt component library.

Each primitive sets its own complete stylesheet at construction time using
design tokens, making it immune to Qt CSS cascade failures caused by
WA_TranslucentBackground on ancestor widgets.

Exports:
    UIButton          — QPushButton with variant + size
    UIChromeFrame     — opaque QFrame for app chrome (translucency-immune)
    UIInput           — QLineEdit
    UISpinBox         — QSpinBox
    UIDoubleSpinBox   — QDoubleSpinBox
    UILabel           — QLabel with semantic variants
    UICard            — QFrame card with header/body/footer slots + variant
    UIDropdownMenu    — QMenu wrapper with Radix-style fluent build API
    attach_context_menu — bind a UIDropdownMenu to a widget's right-click
"""

from gamepad_midi_bridge.ui.primitives.button import UIButton
from gamepad_midi_bridge.ui.primitives.card import UICard
from gamepad_midi_bridge.ui.primitives.context_menu import attach_context_menu
from gamepad_midi_bridge.ui.primitives.dropdown import UIDropdownMenu
from gamepad_midi_bridge.ui.primitives.frame import UIChromeFrame
from gamepad_midi_bridge.ui.primitives.input import UIDoubleSpinBox, UIInput, UISpinBox
from gamepad_midi_bridge.ui.primitives.label import UILabel

__all__ = [
    "UIButton",
    "UICard",
    "UIChromeFrame",
    "UIDoubleSpinBox",
    "UIDropdownMenu",
    "UIInput",
    "UILabel",
    "UISpinBox",
    "attach_context_menu",
]
