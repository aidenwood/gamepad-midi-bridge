# Styling Reference — Universal Controller MIDI

Single source of truth: `src/gamepad_midi_bridge/ui/styles.qss`.

This file maps every objectName the Python code assigns to its widget class,
source file, and the section in `styles.qss` that styles it. Edit visual rules
in `styles.qss` — that's the supported workflow. Don't reach for inline
`setStyleSheet` unless the value is genuinely runtime / data-driven (and even
then, prefer a Qt dynamic property + a `QWidget[state="..."]` selector).

## How to retheme

1. Open `src/gamepad_midi_bridge/ui/styles.qss`.
2. Find the relevant section banner (numbered 1–30).
3. Edit the rule. Save. Relaunch the app — `bash scripts/smoke_test_app.sh 6`.

## ObjectName → widget table

| objectName | Widget class | File | styles.qss section |
|---|---|---|---|
| ChromeWidget | QFrame | src/gamepad_midi_bridge/ui/main_window.py | 1. Global base styles |
| StatusBar | QFrame | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| StatusTitle | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| StatusSub | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| StatusRateLabel | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| ActivityDot | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| PanicButton | QPushButton | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| RecordButton | QPushButton | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| StatusDivider | QFrame | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| LayoutToggle | QPushButton | src/gamepad_midi_bridge/ui/main_window.py | 3. Top status bar |
| PrimaryButton | QPushButton | (shared, many files) | 1. Global base styles |
| StopButton | QPushButton | (shared, many files) | 1. Global base styles |
| UpdateBanner | QFrame | src/gamepad_midi_bridge/ui/main_window.py | 4. Update banner |
| UpdateBannerLabel | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 4. Update banner |
| UpdateBannerOpenButton | QPushButton | src/gamepad_midi_bridge/ui/main_window.py | 4. Update banner |
| UpdateBannerDismissButton | QPushButton | src/gamepad_midi_bridge/ui/main_window.py | 4. Update banner |
| SplitViewHeader | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 5. Side panel + split view picker |
| SplitViewPicker | QComboBox | src/gamepad_midi_bridge/ui/main_window.py | 5. Side panel + split view picker |
| ProNudgeLabel | QLabel | src/gamepad_midi_bridge/ui/main_window.py | 6. Live tab — pro nudge |
| Inspector | Inspector(QWidget) | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorHeader | QFrame | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorTitle | QLabel | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorCloseButton | QPushButton | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorScroll | QScrollArea | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorBodyHost | QWidget | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorKindChip | QLabel | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorAuthor | QLabel | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorDivider | QFrame | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorStatusChip | QLabel | src/gamepad_midi_bridge/ui/inspector.py | 7. Inspector panel |
| InspectorRendererDivider | QFrame | src/gamepad_midi_bridge/ui/inspector_renderers.py | 7. Inspector panel |
| LogConsoleHeader | QFrame | src/gamepad_midi_bridge/ui/log_console.py | 8. Bottom console panel header |
| LogConsoleTitle | QLabel | src/gamepad_midi_bridge/ui/log_console.py | 8. Bottom console panel header |
| LogConsoleClearButton | QPushButton | src/gamepad_midi_bridge/ui/log_console.py | 8. Bottom console panel header |
| LogConsoleToggleButton | QPushButton | src/gamepad_midi_bridge/ui/log_console.py | 8. Bottom console panel header |
| LogConsoleBody | QPlainTextEdit | src/gamepad_midi_bridge/ui/log_console.py | 8. Bottom console panel header |
| MidiLogPanelHeader | QFrame | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| MidiLogPanelTitle | QLabel | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| MidiLogPanelFilterCombo | QComboBox | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| MidiLogPanelClearButton | QPushButton | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| MidiLogPanelToggleButton | QPushButton | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| MidiLogPanelList | QListWidget | src/gamepad_midi_bridge/ui/midi_log_panel.py | 9. MIDI activity log panel |
| ProLockOverlay | QWidget | src/gamepad_midi_bridge/ui/pro_lock.py | 10. Pro lock overlay |
| ProLockCard | QFrame | src/gamepad_midi_bridge/ui/pro_lock.py | 10. Pro lock overlay |
| ProBadge | QLabel | src/gamepad_midi_bridge/ui/pro_lock.py | 10. Pro lock overlay |
| ProLockTitle | QLabel | src/gamepad_midi_bridge/ui/pro_lock.py | 10. Pro lock overlay |
| ProLockSub | QLabel | src/gamepad_midi_bridge/ui/pro_lock.py | 10. Pro lock overlay |
| ReconnectOverlay | ReconnectOverlay(QWidget) | src/gamepad_midi_bridge/ui/reconnect_overlay.py | 11. Reconnect overlay |
| ReconnectTitle | QLabel | src/gamepad_midi_bridge/ui/reconnect_overlay.py | 11. Reconnect overlay |
| ReconnectSubtitle | QLabel | src/gamepad_midi_bridge/ui/reconnect_overlay.py | 11. Reconnect overlay |
| OnboardingHeading | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingHeadingBig | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingBody | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingHint | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingStatus | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingConnectorRow | QFrame | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingConnectorCheck | QCheckBox | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingConnectorDesc | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingConnectorStatus | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingTriggerModeRow | QFrame | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingTriggerModeName | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingTriggerModeDesc | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingPolarDiagram | QLabel | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingSkipLink | QPushButton | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| OnboardingFooter | QFrame | src/gamepad_midi_bridge/ui/onboarding.py | 12. Onboarding wizard |
| MappingTipStrip | QWidget | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingTipIcon | QLabel | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingTipText | QLabel | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingTipCloseButton | QPushButton | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingDivider | QFrame | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingSectionLabel | QLabel | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| MappingCaptureButton | QPushButton | src/gamepad_midi_bridge/ui/mapping_editor.py | 13. Mapping editor |
| TemplateBuilderSelectionHeader | QLabel | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplateBuilderForm | QFrame | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplateBuilderSaveBinding | QPushButton | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplatesPanel | QFrame | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplatesPanelHeader | QLabel | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplatesPanelScroll | QScrollArea | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplatesPanelCardsHost | QWidget | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplateCard | QFrame | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplateCardName | QLabel | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| TemplateCardDesc | QLabel | src/gamepad_midi_bridge/ui/template_builder_tab.py | 14. Template builder tab |
| VisualiseSubTabs | QTabWidget | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualiseSubTabsBar | QTabBar | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualiseScopeScroll | QScrollArea | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualiseScopeHeading | QLabel | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualisePanelFrame | QFrame | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualiseStatLabel | QLabel | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| VisualiseStatValue | QLabel | src/gamepad_midi_bridge/ui/visualise_tab.py | 15. Visualise tab |
| BluetoothHeader | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothSubLabel | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothDocsLink | QPushButton | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothEmptyState | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothPairedDeviceCard | QFrame | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothPairedDeviceTitle | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothPairedDeviceMeta | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| BluetoothPairedDeviceStatus | QLabel | src/gamepad_midi_bridge/ui/bluetooth_tab.py | 16. Bluetooth tab |
| ConnectorsSectionTitle | QLabel | src/gamepad_midi_bridge/ui/connectors_tab.py | 17. Connectors tab |
| ConnectorsSeparator | QFrame | src/gamepad_midi_bridge/ui/connectors_tab.py | 17. Connectors tab |
| ConnectorsHostCard | QFrame | src/gamepad_midi_bridge/ui/connectors_tab.py | 17. Connectors tab |
| ConnectorsTemplateCard | QFrame | src/gamepad_midi_bridge/ui/connectors_tab.py | 17. Connectors tab |
| HelpCard | QFrame | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpFaqRow | QFrame | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpFaqToggle | QPushButton | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpFaqAnswer | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpLogo3D | Logo3DView(QWidget) | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpShortcutKey | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpShortcutDesc | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpBulletDot | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpBulletText | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpLinksNote | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpVersionLabel | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| HelpVersionValue | QLabel | src/gamepad_midi_bridge/ui/help_tab.py | 18. Help tab |
| LatencyDialog | QDialog | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogTitle | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogSub | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogCard | QWidget | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogPrompt | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogCounter | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogSectionLabel | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| LatencyDialogResultLabel | QLabel | src/gamepad_midi_bridge/ui/latency_dialog.py | 19. Latency dialog |
| TestWizardTitle | QLabel | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| TestWizardSub | QLabel | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| TestWizardProgress | QLabel | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| TestWizardStepFrame | QFrame | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| TestWizardStepLabel | QLabel | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| TestWizardStepCheckmark | QLabel | src/gamepad_midi_bridge/ui/test_wizard.py | 20. Test wizard |
| ActivityTimeline | ActivityTimeline(QWidget) | src/gamepad_midi_bridge/ui/activity_timeline.py | 21. Activity timeline |
| ActivityTimelineTitle | QLabel | src/gamepad_midi_bridge/ui/activity_timeline.py | 21. Activity timeline |
| ActivityTimelineClearButton | QPushButton | src/gamepad_midi_bridge/ui/activity_timeline.py | 21. Activity timeline |
| ActivityTimelineList | QListWidget | src/gamepad_midi_bridge/ui/activity_timeline.py | 21. Activity timeline |
| ActivityTimelineEmptyLabel | QLabel | src/gamepad_midi_bridge/ui/activity_timeline.py | 21. Activity timeline |
| AboutEasterEggConsole | QLabel | src/gamepad_midi_bridge/ui/about_tab.py | 22. Easter egg console |
| CalibrationDialogTitle | QLabel | src/gamepad_midi_bridge/ui/calibration_dialog.py | 23. Small dialogs |
| CalibrationDialogSub | QLabel | src/gamepad_midi_bridge/ui/calibration_dialog.py | 23. Small dialogs |
| CalibrationDialogResult | QLabel | src/gamepad_midi_bridge/ui/calibration_dialog.py | 23. Small dialogs |
| CaptureDialogInstruction | QLabel | src/gamepad_midi_bridge/ui/capture_dialog.py | 23. Small dialogs |
| CaptureDialogPreview | QLabel | src/gamepad_midi_bridge/ui/capture_dialog.py | 23. Small dialogs |
| HapticInputDialogIntro | QLabel | src/gamepad_midi_bridge/ui/haptic_input_dialog.py | 23. Small dialogs |
| CommandPaletteCard | QFrame | src/gamepad_midi_bridge/ui/command_palette.py | 24. Command palette |
| CommandPaletteSearch | QLineEdit | src/gamepad_midi_bridge/ui/command_palette.py | 24. Command palette |
| CommandPaletteList | QListWidget | src/gamepad_midi_bridge/ui/command_palette.py | 24. Command palette |
| CommandPaletteHint | QLabel | src/gamepad_midi_bridge/ui/command_palette.py | 24. Command palette |
| HudPresetLabel | QLabel | src/gamepad_midi_bridge/ui/hud_overlay.py | 25. HUD overlay |
| HudThroughputLabel | QLabel | src/gamepad_midi_bridge/ui/hud_overlay.py | 25. HUD overlay |
| MarketplaceCard | QFrame | src/gamepad_midi_bridge/ui/marketplace_tab.py | 26. Marketplace tab |
| ResponsiveTabBar | QTabBar | src/gamepad_midi_bridge/ui/responsive_tab_widget.py | 27. Responsive tab widget |
| ResponsiveTabPickerCombo | QComboBox | src/gamepad_midi_bridge/ui/responsive_tab_widget.py | 27. Responsive tab widget |
| SettingsDangerZone | QGroupBox | src/gamepad_midi_bridge/ui/settings_panel.py | 28. Settings panel — danger zone |
| ThroughputPanel | ThroughputPanel(QWidget) | src/gamepad_midi_bridge/ui/throughput_panel.py | 29. Throughput panel frame |
| UsageHeatmapLabel | QLabel | src/gamepad_midi_bridge/ui/usage_heatmap.py | 30. Usage heatmap controls |
| UsageHeatmapTitle | QLabel | src/gamepad_midi_bridge/ui/usage_heatmap.py | 30. Usage heatmap controls |
| UsageHeatmapResetButton | QPushButton | src/gamepad_midi_bridge/ui/usage_heatmap.py | 30. Usage heatmap controls |
| UsageHeatmapTop5Title | QLabel | src/gamepad_midi_bridge/ui/usage_heatmap.py | 30. Usage heatmap controls |

## Dynamic-property selectors

Some widgets restyle at runtime by setting a Qt dynamic property. The QSS
selectors below match the property values — `widget.setProperty("state", "ok")`
followed by `widget.style().unpolish(widget); widget.style().polish(widget)`
re-evaluates the rule.

| Selector | Property values | File |
|---|---|---|
| `QLabel#OnboardingStatus[state=...]` | `ok`, `error` | onboarding.py |
| `QLabel#OnboardingConnectorStatus[state=...]` | `missing`, `error` | onboarding.py |
| `QLabel#ReconnectTitle[state=...]` | `success`, `failed` | reconnect_overlay.py |
| `QLabel#InspectorKindChip[variant=...]` | `live` | inspector.py |
| `QLabel#InspectorStatusChip[state=...]` | `installed`, `missing` | inspector.py |
| `QLabel#BluetoothPairedDeviceStatus[state=...]` | `connected`, `paired` | bluetooth_tab.py |
| `QLabel#ConnectorsVerifyChip[verifyState=...]` | `ok`, `fail` | connectors_tab.py |
| `QGroupBox[searchState=...]` | `match`, `dim` | settings_panel.py |

## Intentional inline `setStyleSheet` exceptions

The following inline calls were left in place on purpose. Each has a code comment
nearby explaining why.

### 1. QSplitter handles (main_window.py, 3 calls)

`body_splitter.setStyleSheet`, `content_splitter.setStyleSheet`, and
`_live_splitter.setStyleSheet`. **Do NOT move these to global QSS.** A global
`QSplitter::handle` rule breaks drag dispatch on macOS Qt 6 — the handle gets
the styled bg but mouse events stop firing, so dragging silently does nothing
across the entire app.

### 2. Primitive cascade defence (5 files in `primitives/`)

`UIButton`, `UILabel`, `UIInput` (+ spinboxes), `UICard`, `UIChromeFrame` each
self-style at construction. macOS Qt 6 has a paint-cascade bug under
`WA_TranslucentBackground` ancestors: the global QSS cascade dies and any
descendant relying on it ghosts. These primitives carry their own stylesheet so
they survive the bug. Their docstrings document this in detail.

### 3. Runtime state colour swaps

- `MainWindow._activity_dot.setStyleSheet(...)` — teal/grey pulse every
  outgoing MIDI message + fade after 120 ms.
- `HudOverlay._status_dot.setStyleSheet(...)` — green/grey toggle on
  `set_status(running)`.
- `_apply_font_scale` regex-replaces `font-size: Npx` and re-applies via
  `app.setStyleSheet` + `widget.setStyleSheet`. Keep this machinery; it's how
  the A−/A+ status-bar buttons rescale the whole UI.

### 4. Data-driven dynamic colours

- `template_builder_tab.py` — template card hover ring, tag badge, and Apply
  button all take a tag-specific accent colour from `_TAG_COLORS`. There are
  six tags, each with a different hue; an inline stylesheet with an f-string
  is simpler than generating six per-tag QSS selectors.
- `marketplace_tab.py` — tag filter chips swap between selected (filled) and
  unselected (outlined) using the global ACCENT colour. Three chip styles take
  runtime values, including the per-preset tag chip.
- `connectors_tab.py` — verify chip background is keyed off the verify result
  via `_VERIFY_COLOURS[status]`. The same widget swaps between 4+ states.
- `inspector_renderers.py` — the `_chip` helper takes colour/bg/border as
  args; renderers reuse it for different state chips.
- `connectors_tab.py` — host card installed/not-installed UILabel uses an
  inline override because the underlying `UILabel` primitive self-styles
  (cascade defence) so QSS can't reach it.

### 5. Global stylesheet load (theme.py)

`app.setStyleSheet(qss)` in `theme.py` is the entry point that loads
`styles.qss`. This is the call that makes everything else in this document
work. Leave it alone.

## Adding a new styled widget

1. Pick a descriptive camelCase objectName (e.g. `presetManagerImportButton`).
2. In the Python file: `widget.setObjectName("presetManagerImportButton")`.
3. In `styles.qss`: find the right section banner, add a rule like
   `QPushButton#presetManagerImportButton { ... }`.
4. If the widget can have runtime state, add a dynamic property + selector
   instead of inline restyling.
5. Add the row to the table above.

## Verification

```bash
bash scripts/smoke_test_app.sh 6
# Should print: PASS: app survived 6s (alarm killed a healthy process)
```

If any QSS rule has a typo, the app still launches — Qt is permissive about
QSS syntax. Eyeball the app to confirm the rule applied (right widget, right
colour). For visual diffs across the full app, use Playwright per the project's
visual-verification rule.
