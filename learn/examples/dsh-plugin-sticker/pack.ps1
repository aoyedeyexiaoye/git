# pack.ps1 - build an npm-style tarball without npm
# output: <name>-<version>.tgz with root folder "package/"
param(
    [string]$Source = $PSScriptRoot,
    [string]$OutDir = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'

$pkgPath = Join-Path $Source 'package.json'
if (-not (Test-Path $pkgPath)) { throw "package.json not found: $pkgPath" }
$pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json

# files[] is the whitelist; fall back to a sane default
$files = @($pkg.files)
if (-not $files -or $files.Count -eq 0) {
    $files = @('package.json', 'index.js', 'cordis.patch.yml')
}

$stage = Join-Path $Source '.pack'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
$pkgDir = Join-Path $stage 'package'
New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null

$missing = @()
foreach ($f in $files) {
    $srcPath = Join-Path $Source $f
    if (-not (Test-Path $srcPath)) { $missing += $f; continue }
    $dst = Join-Path $pkgDir $f
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item $srcPath $dst -Recurse -Force
}
if ($missing.Count -gt 0) {
    Remove-Item $stage -Recurse -Force
    throw ("files[] listed but missing: " + ($missing -join ', '))
}

$name = $pkg.name
$ver = $pkg.version
$out = Join-Path $OutDir ("{0}-{1}.tgz" -f $name, $ver)
if (Test-Path $out) { Remove-Item $out -Force }

& tar.exe -czf $out -C $stage package
if ($LASTEXITCODE -ne 0) { Remove-Item $stage -Recurse -Force; throw "tar failed" }
Remove-Item $stage -Recurse -Force

$sizeKb = [math]::Round((Get-Item $out).Length / 1KB, 1)
Write-Host ("[ok] {0} ({1} KB)" -f $out, $sizeKb) -ForegroundColor Green
Write-Host "entries:"
& tar.exe -tzf $out
