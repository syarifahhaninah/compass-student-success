# Compass walkthrough choreography — drives Power BI Desktop on an absolute
# schedule matched to captions.ass. Coordinates are in the 1456x816 reference
# space used throughout the session, scaled to the actual screen.
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Mouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, int data, UIntPtr extra);
    public const uint DOWN = 0x0002, UP = 0x0004, WHEEL = 0x0800;
}
"@
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$sx = $b.Width / 1456.0; $sy = $b.Height / 816.0
$t0 = Get-Date

function At([double]$sec) {
    $target = $t0.AddSeconds($sec)
    $ms = ($target - (Get-Date)).TotalMilliseconds
    if ($ms -gt 0) { Start-Sleep -Milliseconds ([int]$ms) }
}
function MoveTo([int]$x, [int]$y) {
    [Mouse]::SetCursorPos([int]($x * $sx), [int]($y * $sy)) | Out-Null
}
function Click([int]$x, [int]$y) {
    MoveTo $x $y; Start-Sleep -Milliseconds 120
    [Mouse]::mouse_event([Mouse]::DOWN, 0, 0, 0, [UIntPtr]::Zero)
    [Mouse]::mouse_event([Mouse]::UP, 0, 0, 0, [UIntPtr]::Zero)
}
function ScrollDown([int]$x, [int]$y, [int]$ticks) {
    MoveTo $x $y; Start-Sleep -Milliseconds 100
    for ($i = 0; $i -lt $ticks; $i++) {
        [Mouse]::mouse_event([Mouse]::WHEEL, 0, 0, -120, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 350
    }
}

# ---------------- timeline (seconds from recording start) ----------------
At 2;    Click 162 750      # Executive page
At 3.5;  Click 75 38        # Home ribbon (clean state)
At 5;    MoveTo 520 440     # neutral park
At 22;   MoveTo 300 350     # hover success-rate line chart
At 26;   MoveTo 430 330
At 31;   MoveTo 800 360     # hover campus bars
At 35;   MoveTo 850 320
At 40;   Click 333 750      # Advisor triage page
At 44;   MoveTo 700 340     # reasons column
At 48;   MoveTo 700 420
At 52;   ScrollDown 430 450 4
At 58;   MoveTo 120 340     # priority tier column
At 63;   MoveTo 120 430
At 66;   MoveTo 930 620     # caseload balance
At 71;   Click 186 38       # Modeling ribbon
At 75;   Click 518 84       # View as (dialog needs time under recording load)
At 82;   Click 607 343      # Advisor_ADV01 checkbox
At 85;   Click 766 510      # OK
At 95;   MoveTo 135 200     # cards showing reduced numbers
At 99;   MoveTo 327 200
At 105;  Click 1146 133     # Stop viewing
At 109;  Click 75 38        # Home ribbon
At 112;  Click 243 750      # Equity and NBF page
At 116;  MoveTo 160 200     # NBF funding card
At 120;  MoveTo 653 200
At 124;  MoveTo 280 360     # retention by cohort bars
At 129;  MoveTo 280 300
At 133;  MoveTo 830 550     # SEHEEF matrix
At 139;  MoveTo 830 600
At 145;  Click 443 750      # Intervention effectiveness page
At 149;  MoveTo 300 190     # estimator table
At 154;  MoveTo 300 210
At 159;  MoveTo 400 410     # naive vs matched bars
At 165;  MoveTo 500 460
At 170;  MoveTo 900 300     # engagement lines
At 178;  Click 549 750      # Data quality page
At 182;  MoveTo 180 300     # findings table
At 188;  MoveTo 800 370     # issues bars
At 194;  MoveTo 520 440     # park
At 200
Write-Output "choreography complete"
