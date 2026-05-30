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
ACCENT_CORAL   = "#f87171"
ACCENT_AMBER   = "#fbbf24"

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
