<#
    voiceover.ps1 —— 用 Windows 自带语音（SAPI）给视频配音
    用法：
        .\voiceover.ps1 -Video out\show.mp4 -Out out\show_vo.mp4 -ScriptFile lines.txt

    lines.txt（UTF-8）格式，每行：起始秒|文本
        0.6|今天也在认真营业
        6.0|偶尔摸鱼，也是一种态度
        12.0|但一直很可爱

    做法：每句合成 wav → adelay 按起始时间摆放 → amix 混合 → loudnorm 归一化 → 与视频合流（视频流 copy）
#>
param(
    [Parameter(Mandatory)][string]$Video,
    [Parameter(Mandatory)][string]$Out,
    [Parameter(Mandatory)][string]$ScriptFile,
    [string]$Voice = 'Microsoft Huihui Desktop',
    [double]$Rate = 0,          # -10..10，语速
    [int]$Volume = 90,          # 0..100
    [string]$Ffmpeg = 'E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

if (-not (Test-Path $Video)) { throw "视频不存在：$Video" }
if (-not (Test-Path $ScriptFile)) { throw "脚本不存在：$ScriptFile" }

$lines = Get-Content -Path $ScriptFile -Encoding UTF8 |
    Where-Object { $_.Trim() -ne '' -and $_.Trim() -notmatch '^#' } |
    ForEach-Object {
        $p = $_.Split('|', 2)
        if ($p.Count -lt 2) { throw "行格式错误（应为 起始秒|文本）：$_" }
        [pscustomobject]@{ Start = [double]$p[0].Trim(); Text = $p[1].Trim() }
    }

Write-Host ("共 {0} 句，语音：{1}" -f $lines.Count, $Voice) -ForegroundColor Cyan

# 临时目录放在输出文件旁边（%TEMP% 在部分受限环境会拒写）
$tmp = Join-Path (Split-Path -Parent ([IO.Path]::GetFullPath($Out))) (".vo_tmp_" + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$wavs = @()
$i = 0
foreach ($l in $lines) {
    $i++
    $wav = Join-Path $tmp ("line{0:00}.wav" -f $i)
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $synth.SelectVoice($Voice)
        $synth.Rate = $Rate
        $synth.Volume = $Volume
        $synth.SetOutputToWaveFile($wav)
        $synth.Speak($l.Text)
    } finally {
        $synth.Dispose()
    }
    $wavs += [pscustomobject]@{ Path = $wav; Start = $l.Start }
    Write-Host ("  [{0}] {1:N1}s  {2}" -f $i, $l.Start, $l.Text)
}

# 构造 ffmpeg：每个 wav 用 adelay 摆到对应时间点，再 amix
$inputs = @('-i', $Video)
foreach ($w in $wavs) { $inputs += @('-i', $w.Path) }

$filters = @()
for ($k = 0; $k -lt $wavs.Count; $k++) {
    $ms = [int]($wavs[$k].Start * 1000)
    $filters += ("[{0}:a]adelay={1}|{1},volume=1.0[a{2}]" -f ($k + 1), $ms, $k)
}
$mixInputs = ($wavs | ForEach-Object -Begin { $j = 0 } -Process { "[a$j]"; $j++ }) -join ''
$filters += ("{0}amix=inputs={1}:normalize=0,apad=pad_dur=3,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]" -f $mixInputs, $wavs.Count)

$args = @('-y', '-hide_banner', '-loglevel', 'error') + $inputs +
        @('-filter_complex', ($filters -join ';'), '-map', '0:v', '-map', '[aout]',
          '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', $Out)

& $Ffmpeg @args
if ($LASTEXITCODE -ne 0) { throw "ffmpeg 失败（exit $LASTEXITCODE）" }

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
$size = [math]::Round((Get-Item $Out).Length / 1KB, 0)
Write-Host ("[ok] {0}  {1} KB（视频流 copy，未重编码）" -f $Out, $size) -ForegroundColor Green
