"""Design tokens — one source of truth for colours, spacing, type, radii.
Every primitive component imports from here. NEVER hardcode hex colours in
component code — always reference a token. If a colour isn't in this file,
add it here first, then use the name.
"""

# Backgrounds
BG_BASE        = "#0c0d10"
BG_SURFACE     = "#15171d"
BG_ELEVATED    = "#1d2028"
BG_HOVER       = "#22242c"
BG_PRESSED     = "#2a2d36"

# Text
TEXT_PRIMARY   = "#f5f7fa"
TEXT_SECONDARY = "#c2c6cc"
TEXT_MUTED     = "#8a9099"
TEXT_DISABLED  = "#5b6068"

# Accent
ACCENT_TEAL    = "#2dd4bf"
ACCENT_TEAL_FG = "#06070a"
ACCENT_TEAL_DIM = "#123b36"   # lit mapping row — teal at ~15% over BG_SURFACE
ACCENT_CORAL   = "#f87171"
ACCENT_AMBER   = "#fbbf24"

# ── Shell palette (2026-10 UI direction) ─────────────────────────────────
# Read from Aiden's Setup wireframe, named by the role they play there.
# See UI-HANDOVER.md. Purple carries structure, teal carries action — this
# is what resolved the earlier teal-vs-purple-action ambiguity.
#
# These are additive. Nothing in the current app is restyled by their
# existence; they are the vocabulary the new shell is built from, so the
# two can coexist while the redesign lands pass by pass.
SHELL_PURPLE       = "#1B0030"   # shell, panel title bars, alt-row base
SHELL_TEAL         = "#2DD4BF"   # action, selected mode, icon accent
SHELL_BLUE         = "#203F5B"   # secondary header buttons
SHELL_TEAL_UTIL    = "#289494"   # utility controls in panel headers
SHELL_ROW_ALT      = "#3D2A4C"   # alternating table row
SHELL_TABLE_HEAD   = "#330F4F"   # table column header band
SHELL_DESC_BODY    = "#2B034A"   # Description panel body
# Near-black label on teal fill. White on #2DD4BF is ~1.86:1 and fails at
# small sizes; this pair is ~10.8:1 and keeps the wireframe's teal.
SHELL_TEAL_FG      = "#06070A"

# Border / dividers / focus
BORDER_SUBTLE  = "#24262d"
BORDER_STRONG  = "#3a3d46"
FOCUS_RING     = "#5eead4"

# Spacing (4px base)
S_XS, S_S, S_M, S_L, S_XL, S_2XL = 4, 8, 12, 16, 24, 32

# Radii
R_S, R_M, R_L, R_PILL = 4, 8, 12, 999

# Type scale
FS_XS, FS_S, FS_M, FS_L, FS_XL, FS_2XL = 10, 11, 12, 14, 18, 24
FW_REG, FW_MED, FW_BOLD = 400, 600, 700
