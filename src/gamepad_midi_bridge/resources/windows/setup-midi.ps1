<#
.SYNOPSIS
    Universal Controller MIDI — Windows setup assistant.

    One-click MIDI routing setup for non-technical users. The app launches this
    in its own PowerShell window (the "Set up Windows MIDI" button). It checks
    each requirement, fixes what's missing, and re-checks.

    What it does:
      1. Checks for loopMIDI; if missing, downloads + silent-installs it.
      2. Ensures a loopMIDI port named "Universal Controller MIDI" exists, so the
         app's auto-detect routes to it (the app already matches any loopMIDI
         port by name).
      3. Reports PASS/FAIL per requirement.

    Downloading loopMIDI at runtime (vs bundling it) means we never redistribute
    it — sidesteps loopMIDI's licensing entirely.

.NOTES
    Run from the app:
      powershell.exe -ExecutionPolicy Bypass -NoProfile -File setup-midi.ps1
    Installing loopMIDI needs elevation — the script self-elevates for that step.

    NOT YET VERIFIED ON A REAL WINDOWS BOX. The loopMIDI silent-install switches
    and the port-creation registry path are best-effort and MUST be confirmed on
    Windows before shipping. Flagged inline with "VERIFY:".
#>

[CmdletBinding()]
param(
    [string]$PortName = "Universal Controller MIDI",
    # Official loopMIDI download. VERIFY: pin to a known-good versioned URL once chosen.
    [string]$LoopMidiUrl = "https://www.tobias-erichsen.de/software/loopmidi/loopMIDISetup.zip"
)

$ErrorActionPreference = "Stop"

function Write-Step    { param($m) Write-Host "`n>> $m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "  [PASS] $m" -ForegroundColor Green }
function Write-Fail    { param($m) Write-Host "  [FAIL] $m" -ForegroundColor Red }
function Write-Info    { param($m) Write-Host "  $m" -ForegroundColor Gray }

# --- requirement checks -----------------------------------------------------

function Test-LoopMidiInstalled {
    # loopMIDI installs to Program Files and registers an uninstall entry.
    $exe = Join-Path ${env:ProgramFiles(x86)} "Tobias Erichsen\loopMIDI\loopMIDI.exe"
    if (Test-Path $exe) { return $exe }
    $exe = Join-Path $env:ProgramFiles "Tobias Erichsen\loopMIDI\loopMIDI.exe"
    if (Test-Path $exe) { return $exe }
    return $null
}

function Get-MidiOutputPorts {
    # Query the multimedia API (winmm) for MIDI output device names. This is the
    # same list the app's rtmidi backend sees.
    if (-not ("UcmMidi.Winmm" -as [type])) {
        Add-Type -Namespace UcmMidi -Name Winmm -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("winmm.dll")]
public static extern uint midiOutGetNumDevs();

[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, CharSet=System.Runtime.InteropServices.CharSet.Auto)]
public struct MIDIOUTCAPS {
    public ushort wMid;
    public ushort wPid;
    public uint vDriverVersion;
    [System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.ByValTStr, SizeConst=32)]
    public string szPname;
    public ushort wTechnology;
    public ushort wVoices;
    public ushort wNotes;
    public ushort wChannelMask;
    public uint dwSupport;
}

[System.Runtime.InteropServices.DllImport("winmm.dll", CharSet=System.Runtime.InteropServices.CharSet.Auto)]
public static extern uint midiOutGetDevCaps(System.UIntPtr uDeviceID, ref MIDIOUTCAPS lpCaps, uint cbCaps);
"@
    }
    $names = @()
    $count = [UcmMidi.Winmm]::midiOutGetNumDevs()
    for ($i = 0; $i -lt $count; $i++) {
        $caps = New-Object UcmMidi.Winmm+MIDIOUTCAPS
        $size = [System.Runtime.InteropServices.Marshal]::SizeOf($caps)
        [void][UcmMidi.Winmm]::midiOutGetDevCaps([UIntPtr]::new($i), [ref]$caps, $size)
        $names += $caps.szPname
    }
    return $names
}

function Test-PortExists {
    param($Name)
    $ports = Get-MidiOutputPorts
    return [bool]($ports | Where-Object { $_ -like "*$Name*" -or $_ -like "*loopMIDI*" })
}

# --- fix steps --------------------------------------------------------------

$LoopMidiPage = "https://www.tobias-erichsen.de/software/loopmidi.html"

function Open-LoopMidiPageFallback {
    param($Reason)
    Write-Info "Automatic install unavailable ($Reason)."
    Write-Info "Opening the official loopMIDI page — install it (Next > Next > Finish),"
    Write-Info "then return here and press Re-check."
    Start-Process $LoopMidiPage
}

function Install-LoopMidi {
    Write-Step "Installing loopMIDI"
    $tmp = Join-Path $env:TEMP "ucm-loopmidi"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $zip = Join-Path $tmp "loopMIDISetup.zip"

    # VERIFY (needs a Windows box): the download URL must be pinned to a current
    # versioned zip on tobias-erichsen.de, and the Inno Setup silent switches
    # confirmed. If ANYTHING here fails we fall back to opening the official page
    # so the user is never dead-ended — degrade, don't crash.
    try {
        Write-Info "Downloading loopMIDI..."
        Invoke-WebRequest -Uri $LoopMidiUrl -OutFile $zip -UseBasicParsing -TimeoutSec 30
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        $setup = Get-ChildItem -Path $tmp -Filter "*.exe" -Recurse | Select-Object -First 1
        if (-not $setup) { Open-LoopMidiPageFallback "installer not found in archive"; return }

        Write-Info "Running installer (a UAC prompt will appear — click Yes)"
        Start-Process -FilePath $setup.FullName `
            -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES" `
            -Verb RunAs -Wait -ErrorAction Stop
    }
    catch {
        Open-LoopMidiPageFallback $_.Exception.Message
    }
}

function New-LoopMidiPort {
    param($Name)
    Write-Step "Bringing up a loopMIDI routing port"
    $exe = Test-LoopMidiInstalled
    if (-not $exe) { throw "loopMIDI is not installed; cannot create the port." }

    # We do NOT need a port named exactly "$Name": the app auto-detects ANY
    # loopMIDI port (it matches "loopmidi" in the device name). loopMIDI also
    # restores whatever ports existed at its last exit. So the robust play is
    # simply to launch loopMIDI and let its default port come up — far more
    # reliable than poking its registry config, which has no documented schema.
    if (-not (Get-Process -Name "loopMIDI" -ErrorAction SilentlyContinue)) {
        Write-Info "Launching loopMIDI..."
        Start-Process -FilePath $exe
        Start-Sleep -Seconds 3
    }

    # Re-enumerate after launch — most installs expose a default "loopMIDI Port".
    if (Test-PortExists -Name $Name) {
        Write-Ok "A loopMIDI port is now available"
        return
    }

    # No port yet (some loopMIDI builds start empty). One-time, ~5-second manual
    # step — and ANY name works, so we don't make the user match a string.
    Write-Info "loopMIDI is open but has no port yet. In its window:"
    Write-Info "  1. Type any name (e.g. '$Name') in the 'New port-name' box"
    Write-Info "  2. Click the [ + ] button"
    Write-Info "Then come back here and press Re-check in the app."
    throw "Add one port in loopMIDI (any name), then re-check."
}

# --- main -------------------------------------------------------------------

Write-Host "Universal Controller MIDI — Windows MIDI setup" -ForegroundColor White
Write-Host "================================================"

$allOk = $true

Write-Step "Checking loopMIDI"
$loopExe = Test-LoopMidiInstalled
if ($loopExe) {
    Write-Ok "loopMIDI installed ($loopExe)"
} else {
    Write-Fail "loopMIDI not found"
    Install-LoopMidi
    if (Test-LoopMidiInstalled) {
        Write-Ok "loopMIDI installed"
    } else {
        Write-Info "Finish the loopMIDI install (the page just opened), then press Re-check."
        $allOk = $false
    }
}

Write-Step "Checking MIDI routing port"
if (Test-PortExists -Name $PortName) {
    Write-Ok "A loopMIDI / '$PortName' port is available"
} else {
    Write-Fail "No routing port found"
    try { New-LoopMidiPort -Name $PortName }
    catch { Write-Fail "Port setup failed: $($_.Exception.Message)"; $allOk = $false }
    if (Test-PortExists -Name $PortName) { Write-Ok "Routing port available" }
    else { Write-Info "Port not detected yet — add it in loopMIDI, then re-run."; $allOk = $false }
}

Write-Step "Opening the helper apps"
# loopMIDI must be running for its port to exist. DS4Windows is optional — open
# it if the user has it installed (helps SDL read the pad reliably).
function Open-IfPresent {
    param($Label, $ProcName, $Paths)
    if (Get-Process -Name $ProcName -ErrorAction SilentlyContinue) {
        Write-Ok "$Label already running"; return
    }
    $exe = $Paths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($exe) { Start-Process -FilePath $exe; Write-Ok "$Label opened" }
    else { Write-Info "$Label not installed (optional) — skipping" }
}
Open-IfPresent "loopMIDI" "loopMIDI" @(
    (Join-Path ${env:ProgramFiles(x86)} "Tobias Erichsen\loopMIDI\loopMIDI.exe"),
    (Join-Path $env:ProgramFiles "Tobias Erichsen\loopMIDI\loopMIDI.exe"))
Open-IfPresent "DS4Windows" "DS4Windows" @(
    (Join-Path $env:ProgramFiles "DS4Windows\DS4Windows.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "DS4Windows\DS4Windows.exe"),
    (Join-Path $env:LOCALAPPDATA "DS4Windows\DS4Windows.exe"))

Write-Host "`n================================================"
if ($allOk) {
    Write-Host "All set. Open Universal Controller MIDI and click Start." -ForegroundColor Green
} else {
    Write-Host "Some steps need attention — see [FAIL] lines above." -ForegroundColor Yellow
}
Write-Host "`nPress Enter to close..." -ForegroundColor Gray
[void](Read-Host)
