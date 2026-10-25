# Prepares this PC to join a LAN co-op game (run by "Join LAN co-op.cmd"):
#  1. finds the host on the network (or uses -HostAddress),
#  2. fetches the host's newest save into the co-op profile, so both players start from the same save,
#  3. gives the co-op profile copies of this PC's Witcher 3 settings the first time,
#  4. writes bin\WitcherOnline\config.xml (member role, co-op profile on, the save to load at the main menu).
# The player's own Documents\The Witcher 3 (settings and saves) is only read, never changed.
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$HostAddress = 'auto',
    [int]$Port = 40000
)
$ErrorActionPreference = 'Continue'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$woDir = Join-Path $here '..\WitcherOnline'
$profileW3 = Join-Path $woDir 'coop-profile\The Witcher 3'
$saves = Join-Path $profileW3 'gamesaves'
New-Item -ItemType Directory -Force $saves | Out-Null

# 1. the host: a broadcast the server answers straight back (Windows Firewall lets that answer in)
$crashPort = 40003
if ($HostAddress -eq 'auto' -or $HostAddress -eq '') {
    Write-Host 'Looking for the host on the network...'
    $udp = New-Object System.Net.Sockets.UdpClient
    $udp.EnableBroadcast = $true
    $udp.Client.ReceiveTimeout = 1000
    $query = [Text.Encoding]::UTF8.GetBytes("DISCOVER`tW3COOP`t1")
    $found = $null
    for ($i = 0; $i -lt 30 -and -not $found; $i++) {
        [void]$udp.Send($query, $query.Length, (New-Object System.Net.IPEndPoint ([Net.IPAddress]::Broadcast), $Port))
        try {
            $from = New-Object System.Net.IPEndPoint ([Net.IPAddress]::Any), 0
            $reply = [Text.Encoding]::UTF8.GetString($udp.Receive([ref]$from)).Split("`t")
            if ($reply[0] -eq 'W3COOP_HOST') {
                $found = $from.Address.ToString()
                $Port = [int]$reply[3]
                if ($reply.Length -ge 6) { $crashPort = [int]$reply[5] }
                Write-Host "Found the host at $found (W3Coop $($reply[2]))."
            }
        } catch { }
    }
    $udp.Close()
    if ($found) { $HostAddress = $found }
    else {
        Write-Host 'No host answered yet. The game will keep looking when it starts; the save could not be fetched.'
        $HostAddress = 'auto'
    }
}

# 2. the host's newest save
$autoLoad = ''
if ($HostAddress -ne 'auto' -and $crashPort -gt 0) {
    $base = "http://${HostAddress}:$crashPort/save/latest"
    try {
        $info = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 "$base/info").Content.Trim().Split("`t")
        $file = $info[0]
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 "$base/sav" -OutFile (Join-Path $saves $file)
        try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 "$base/png" -OutFile (Join-Path $saves ([IO.Path]::ChangeExtension($file, '.png'))) } catch { }
        $got = (Get-Item (Join-Path $saves $file)).Length
        if ($got -eq [long]$info[1]) {
            $autoLoad = [IO.Path]::GetFileNameWithoutExtension($file)
            Write-Host "Fetched the host's save $file ($([math]::Round($got / 1MB, 1)) MB); the game loads it at the main menu."
        } else {
            Write-Host "The host's save arrived incomplete ($got of $($info[1]) bytes); load a save yourself."
        }
    } catch {
        Write-Host "Could not fetch the host's save ($($_.Exception.Message)); load a save yourself."
    }
}

# 3. settings for the co-op profile, copied once from this PC's own game
$ownW3 = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'The Witcher 3'
foreach ($f in 'dx12user.settings', 'input.settings', 'profile.settings', 'mods.settings') {
    $src = Join-Path $ownW3 $f
    $dst = Join-Path $profileW3 $f
    if ((Test-Path $src) -and -not (Test-Path $dst)) { Copy-Item $src $dst }
}

# 4. config.xml
$xml = @"
<?xml version="1.0"?>
<Config>
	<Username>$([Security.SecurityElement]::Escape($Name))</Username>
	<ServerIP>$HostAddress</ServerIP>
	<Port>$Port</Port>
	<Role>member</Role>
	<CoopProfile>true</CoopProfile>
	<AutoLoadSave>$([Security.SecurityElement]::Escape($autoLoad))</AutoLoadSave>
</Config>
"@
Set-Content -Path (Join-Path $woDir 'config.xml') -Value $xml -Encoding UTF8
Write-Host 'Ready.'
