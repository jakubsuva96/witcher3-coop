# Witcher 3 co-op na domácí síti. Host: server + sdílení poslední uložené hry. Join: najde hosta, stáhne jeho
# uloženou hru do co-op slotu (vlastní uložené hry se nemění), nastaví config a spustí hru.
param(
    [Parameter(Mandatory = $true)][ValidateSet('host', 'join')][string]$Mode,
    [string]$HostAddress = '',
    [switch]$NoGame
)

$ErrorActionPreference = 'Stop'
$GamePort = 40000
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$GameRoot = (Resolve-Path (Join-Path $Here '..\..')).Path
$ConfigPath = Join-Path $GameRoot 'bin\WitcherOnline\config.xml'
$GameExe = Join-Path $GameRoot 'bin\x64_dx12\witcher3.exe'
$W3Docs = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'The Witcher 3'
$SavesDir = Join-Path $W3Docs 'gamesaves'
$SlotRecord = Join-Path $W3Docs 'w3coop-slot.txt'

function Say([string]$text, [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Fail([string]$text) { Say ''; Say $text 'Red'; Say ''; Read-Host 'Stiskni Enter pro zavření' | Out-Null; exit 1 }

function Get-Username
{
    if (Test-Path $ConfigPath)
    {
        $name = ([xml](Get-Content -Raw $ConfigPath)).Config.Username
        if ($name) { return $name }
    }
    return $env:USERNAME
}

function Write-Config([string]$name, [string]$serverIp)
{
    $xml = "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`r`n<Config>`r`n    <Username>$name</Username>`r`n    <ServerIP>$serverIp</ServerIP>`r`n    <Port>$GamePort</Port>`r`n</Config>`r`n"
    [IO.File]::WriteAllText($ConfigPath, $xml, (New-Object Text.UTF8Encoding $false))
}

function Start-Game
{
    if ($NoGame) { return }
    if (Get-Process witcher3 -ErrorAction SilentlyContinue) { Say 'Hra už běží.' 'Yellow'; return }
    if (-not (Test-Path $GameExe)) { Say "Nenašel jsem hru: $GameExe" 'Red'; return }
    Start-Process -FilePath $GameExe -WorkingDirectory (Split-Path $GameExe)
    Say 'Spouštím Zaklínače 3...' 'Green'
}

function Get-BroadcastAddresses
{
    $list = @('255.255.255.255')
    foreach ($ip in Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    {
        if ($ip.IPAddress -like '127.*' -or $ip.IPAddress -like '169.254.*' -or $ip.PrefixLength -ge 32) { continue }
        $bytes = [Net.IPAddress]::Parse($ip.IPAddress).GetAddressBytes()
        $octets = for ($i = 0; $i -lt 4; $i++)
        {
            $bits = [math]::Max(0, [math]::Min(8, $ip.PrefixLength - 8 * $i))
            $m = (0xFF -shl (8 - $bits)) -band 0xFF
            ($bytes[$i] -band $m) -bor ((-bnot $m) -band 0xFF)
        }
        $list += ($octets -join '.')
    }
    return $list | Select-Object -Unique
}

# Returns @{ Ip; SavePort } or $null. With a fixed address it asks only that one.
function Find-Host([string]$fixed, [int]$seconds)
{
    $udp = New-Object Net.Sockets.UdpClient 0
    $udp.EnableBroadcast = $true
    $udp.Client.ReceiveTimeout = 1000
    $probe = [Text.Encoding]::UTF8.GetBytes("DISCOVER`tW3COOP`t1")
    $targets = if ($fixed) { @($fixed) } else { Get-BroadcastAddresses }
    $deadline = (Get-Date).AddSeconds($seconds)
    try
    {
        while ((Get-Date) -lt $deadline)
        {
            foreach ($t in $targets) { try { [void]$udp.Send($probe, $probe.Length, $t, $GamePort) } catch { } }
            $end = (Get-Date).AddMilliseconds(1000)
            while ((Get-Date) -lt $end)
            {
                try
                {
                    $from = New-Object Net.IPEndPoint ([Net.IPAddress]::Any, 0)
                    $parts = [Text.Encoding]::UTF8.GetString($udp.Receive([ref]$from)).Split("`t")
                    if ($parts[0] -eq 'W3COOP_HOST')
                    {
                        return @{ Ip = $from.Address.ToString(); SavePort = [int]$parts[4] }
                    }
                }
                catch [Net.Sockets.SocketException] { }
            }
            Write-Host '.' -NoNewline
        }
    }
    finally { $udp.Close() }
    return $null
}

# Replaces only the files this launcher put there last time; a same-named file it didn't write is left alone.
function Install-CoopSave([string]$zipPath)
{
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Force $SavesDir | Out-Null

    if (Test-Path $SlotRecord)
    {
        foreach ($old in Get-Content $SlotRecord)
        {
            $p = Join-Path $SavesDir $old
            if ($old -and (Test-Path -LiteralPath $p)) { Remove-Item -LiteralPath $p -Force }
        }
    }

    $written = @()
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try
    {
        foreach ($entry in $zip.Entries)
        {
            $name = [IO.Path]::GetFileName($entry.FullName)
            if ($name -notmatch '^[\w\-]+\.(sav|png|json)$') { continue }
            $dest = Join-Path $SavesDir $name
            if (Test-Path -LiteralPath $dest) { Say "Soubor $name už v uložených hrách je, nechávám ho být." 'Yellow'; continue }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest)
            (Get-Item -LiteralPath $dest).LastWriteTime = Get-Date
            $written += $name
        }
    }
    finally { $zip.Dispose() }

    Set-Content -LiteralPath $SlotRecord -Value $written -Encoding UTF8
    return $written
}

$host.UI.RawUI.WindowTitle = "Zaklínač 3 co-op ($Mode)"
$name = Get-Username

if ($Mode -eq 'host')
{
    if (-not (Get-Command java -ErrorAction SilentlyContinue)) { Fail 'Hostování potřebuje Javu 21 nebo novější: https://adoptium.net' }
    if (Get-CimInstance Win32_Process -Filter "Name='java.exe'" | Where-Object { $_.CommandLine -match 'WitcherServer\.jar' })
    {
        Fail 'Co-op server už běží v jiném okně. Zavři ho a spusť tohle znovu.'
    }

    Write-Config $name '127.0.0.1'
    Say "Hostuješ jako $name." 'Green'
    Say 'Adresy tohoto PC v síti:'
    Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        ForEach-Object { Say ("  {0}  ({1})" -f $_.IPAddress, $_.InterfaceAlias) }

    Say ''
    Say "Kdyby druhému hráči nešla stáhnout tvoje uložená hra, povol jednou ve firewallu TCP $($GamePort + 1)" 'DarkGray'
    Say '(pravý klik na Start > Terminál (správce)):' 'DarkGray'
    Say "  netsh advfirewall firewall add rule name=`"W3 Co-op save`" dir=in action=allow protocol=TCP localport=$($GamePort + 1)" 'DarkGray'

    Say ''
    Say 'Nech tohle okno otevřené, dokud hrajete. Zavřením okna co-op skončí.' 'Green'
    Say 'Druhý hráč spustí "Join LAN co-op.cmd" a připojí se sám.'
    Say ''
    Start-Game
    & java -jar (Join-Path $Here 'server\WitcherServer.jar') $GamePort --saves $SavesDir
    Read-Host 'Server skončil. Stiskni Enter pro zavření' | Out-Null
    exit 0
}

Say "Připojuješ se jako $name." 'Green'
if ($HostAddress) { Write-Host "Hledám hosta na $HostAddress " -NoNewline } else { Write-Host 'Hledám hosta v síti (až 3 minuty, host může startovat později) ' -NoNewline }
$found = Find-Host $HostAddress 180
Say ''
if (-not $found)
{
    Fail ("Hosta jsem nenašel. Zkontroluj:`n" +
          "  - běží u hosta okno `"Host LAN co-op`"?`n" +
          "  - jste na stejné Wi-Fi / síti?`n" +
          "  - má host ve firewallu povolený UDP port $GamePort?")
}
Say "Host nalezen: $($found.Ip)" 'Green'
Write-Config $name $found.Ip

function Get-HostSave([string]$saveBase)
{
    $zip = Join-Path $env:TEMP 'w3coop-save.zip'
    $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 -Uri "$saveBase/save" -OutFile $zip -PassThru
    $files = Install-CoopSave $zip
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    if ($files.Count -gt 0) { return $resp.Headers['X-Save-Name'] }
    return ''
}

$installed = ''
$saveBase = "http://$($found.Ip):$($found.SavePort)"
if ($found.SavePort -gt 0)
{
    try
    {
        $installed = Get-HostSave $saveBase
        if ($installed)
        {
            Say "Hostova uložená hra je v co-op slotu: $installed" 'Green'
            Say 'Ve hře dej Načíst hru a vyber nejnovější uloženou hru (nahoře). Tvoje vlastní uložené hry zůstaly beze změny.'
        }
    }
    catch
    {
        Say "Uloženou hru od hosta se nepodařilo stáhnout: $($_.Exception.Message)" 'Yellow'
        Say "Host musí mít ve firewallu povolený TCP port $($found.SavePort) (vypíše mu to jeho okno). Hrát jde i tak." 'Yellow'
    }
}
else
{
    Say 'Host nesdílí uloženou hru (starší server). Hrát jde i tak.' 'Yellow'
}

Say ''
Start-Game
if ($NoGame -or $found.SavePort -le 0) { Start-Sleep -Seconds 5; exit 0 }

# Keeps the co-op slot on the host's newest save while the game runs: resync and the host's death load it.
Say 'Nech tohle okno otevřené, dokud hraješ: průběžně si bere hostovy nové uložené hry pro resync.' 'Green'
Start-Sleep -Seconds 20
while (Get-Process witcher3 -ErrorAction SilentlyContinue)
{
    try
    {
        $latest = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "$saveBase/save/name").Content.Trim()
        if ($latest -and $latest -ne $installed)
        {
            $got = Get-HostSave $saveBase
            if ($got) { $installed = $got; Say ("{0:HH:mm} nová uložená hra od hosta: {1}" -f (Get-Date), $got) }
        }
    }
    catch { }
    Start-Sleep -Seconds 10
}
Say 'Hra skončila.'
Start-Sleep -Seconds 3
