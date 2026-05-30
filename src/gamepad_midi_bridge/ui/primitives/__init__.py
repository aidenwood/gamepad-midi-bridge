"""UI primitives — Radix-for-Qt component library.

Each primitive sets its own complete stylesheet at construction time using
design tokens, making it immune to Qt CSS cascade failures caused by
WA_TranslucentBackground on ancestor widgets.

Exports:
    UIButton        — QPushButton with variant + size
    UIInput         — QLineEdit
    UISpinBox       — QSpinBox
    UIDoubleSpinBox — QDoubleSpinBox
    UILabel         — QLabel with semantic variants
    UICard          — QFrame card container
"""

from gamepad_midi_bridge.ui.primitives.button import UIButton
from gamepad_midi_bridge.ui.primitives.card import UICard
from gamepad_midi_bridge.ui.primitives.input import UIDoubleSpinBox, UIInput, UISpinBox
from gamepad_midi_bridge.ui.primitives.label import UILabel

__all__ = [
    "UIButton",
    "UICard",
    "UIDoubleSpinBox",
    "UIInput",
    "UILabel",
    "UISpinBox",
]
