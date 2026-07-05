# Capture the Power BI report canvas region to a PNG (crops window chrome).
# Usage: powershell -File capture.ps1 -Out <path>
param([Parameter(Mandatory=$true)][string]$Out)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
# Reference coords measured on a 1456x816 downsampled screenshot
$sx = $b.Width / 1456.0; $sy = $b.Height / 816.0
$x = [int](30 * $sx); $y = [int](125 * $sy)
$w = [int](1000 * $sx); $h = [int](613 * $sy)
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out"
