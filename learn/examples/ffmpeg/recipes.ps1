<#
    ffmpeg 常用剪辑配方（PowerShell 版）
    用法：
        .\recipes.ps1 -Action trim   -In a.mp4 -Out b.mp4 -Start 1 -Duration 3
        .\recipes.ps1 -Action speed  -In a.mp4 -Out b.mp4 -Rate 2
        .\recipes.ps1 -Action concat -In "a.mp4,b.mp4" -Out c.mp4
        .\recipes.ps1 -Action text   -In a.mp4 -Out b.mp4 -Text "hello"
        .\recipes.ps1 -Action gif    -In a.mp4 -Out b.gif
        .\recipes.ps1 -Action frame  -In a.mp4 -Out b.png -At 1
    说明：命令全部来自 learn/04-ffmpeg.md，本机实测通过。
    注意：本文件必须保存为 UTF-8 with BOM，否则 PS5.1 会把中文当 ANSI 读，直接语法报错。
#>
param(
    [Parameter(Mandatory)][ValidateSet('trim', 'speed', 'concat', 'text', 'gif', 'frame')][string]$Action,
    [Parameter(Mandatory)][string]$In,
    [Parameter(Mandatory)][string]$Out,
    [double]$Start = 0,
    [double]$Duration = 0,
    [double]$Rate = 2,
    [string]$Text = '',
    [double]$At = 1,
    [string]$Ffmpeg = 'E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe'
)

if (-not (Test-Path $Ffmpeg)) {
    $py = 'E:\AI\Deepseek1\py310\python.exe'
    $Ffmpeg = & $py -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>$null
    if (-not $Ffmpeg) { throw "ffmpeg not found: pip install imageio-ffmpeg" }
}

$common = @('-y', '-hide_banner', '-loglevel', 'error')

switch ($Action) {
    'trim' {
        $ffArgs = $common + @('-ss', $Start, '-i', $In) + $(if ($Duration -gt 0) { @('-t', $Duration) } else { @() }) + @('-c', 'copy', $Out)
    }
    'speed' {
        $setpts = 1 / $Rate
        $ffArgs = $common + @('-i', $In, '-filter_complex',
            "[0:v]setpts=${setpts}*PTS[v];[0:a]atempo=$Rate[a]",
            '-map', '[v]', '-map', '[a]', $Out)
    }
    'concat' {
        $list = Join-Path ([IO.Path]::GetTempPath()) ("ffconcat_" + [guid]::NewGuid().ToString('N') + ".txt")
        ($In -split ',' | ForEach-Object { "file '$_'" }) | Set-Content -Path $list -Encoding ASCII
        $ffArgs = $common + @('-f', 'concat', '-safe', '0', '-i', $list, '-c', 'copy', $Out)
    }
    'text' {
        $vf = "drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='$Text':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-80"
        $ffArgs = $common + @('-i', $In, '-vf', $vf, '-c:a', 'copy', $Out)
    }
    'gif' {
        $ffArgs = $common + @('-i', $In, '-vf', 'fps=10,scale=320:-1:flags=lanczos', $Out)
    }
    'frame' {
        $ffArgs = $common + @('-ss', $At, '-i', $In, '-vframes', '1', $Out)
    }
}

Write-Host "[ffmpeg] $Action : $In -> $Out" -ForegroundColor Cyan
& $Ffmpeg @ffArgs
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed (exit $LASTEXITCODE)" }
if (-not (Test-Path $Out)) { throw "output not created" }
Write-Host ("[ok] {0} {1:N0} KB" -f $Out, ((Get-Item $Out).Length / 1KB)) -ForegroundColor Green
