<#
.SYNOPSIS
    The desk's public front doors: help.pmcne.net and desk.pmcne.net, reached only
    through the Cloudflare tunnel on this machine. Preview by default.

.DESCRIPTION
    Dada, 9 Oct 2026: "lets get the ticketing live online on the web through my
    cloudflare", then "make sure to use a diff site it may cause split brain on
    internal network". So the public names are on a domain the internal DNS does
    not serve (pmcne.net), and each has its own IIS site, apart from the LAN's
    PSA-Portal and PSA-Desk, which are not touched.

    Each public site:
      - binds plain http on the LOOPBACK address only (127.0.0.1:8091 and :8092),
        so nothing on the network can reach it. cloudflared, on this machine, is
        its only client; the tunnel and Cloudflare carry TLS from there out.
      - forwards to the desk on 127.0.0.1:8085 exactly as the LAN sites do, but
        tells the desk the INTERNAL name in X-Forwarded-Host. The desk decides
        "requester portal or technician desk" from that name (Config.is_portal_host),
        so it behaves exactly as it does on the LAN.
      - translates the browser's Origin header ONLY when it is exactly this public
        site's own origin, to the internal one. Without that, the desk refuses
        every sign-in from the new name with 403 ("posted from another site"),
        because it accepts only the two origins it was configured with. Any other
        origin passes through untouched, so a form posted from a foreign site is
        still refused.
      - refuses /api/ outright. That is the machine API (monitoring, the archive);
        no page uses it and no machine outside the LAN needs it.
      - marks every cookie Secure, as the LAN sites do.

    Nothing here publishes a DNS record or starts the tunnel.

.EXAMPLE
    .\New-PsaPublicIis.ps1            # preview: says what it would make
    .\New-PsaPublicIis.ps1 -Apply     # make it
#>
[CmdletBinding()]
param([switch] $Apply)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
Import-Module WebAdministration

$Desk = 'http://127.0.0.1:8085'
$Sites = @(
    @{ Name = 'PSA-Portal-Public'; Public = 'help.pmcne.net'; Internal = 'help.pmcne.ph'; Port = 8091; Path = 'C:\inetpub\psa-portal-public' },
    @{ Name = 'PSA-Desk-Public';   Public = 'desk.pmcne.net'; Internal = 'desk.pmcne.ph'; Port = 8092; Path = 'C:\inetpub\psa-desk-public' }
)

function Get-WebConfigText($s) {
    $originPattern = '^https://' + [regex]::Escape($s.Public) + '$'
    return @"
<?xml version="1.0" encoding="UTF-8"?>
<!-- $($s.Name): https://$($s.Public) from the Cloudflare tunnel only (loopback binding) -> the desk on $Desk,
     told it is $($s.Internal). Made by New-PsaPublicIis.ps1. Every rule here applies to this site only. -->
<configuration>
  <system.webServer>
    <security>
      <requestFiltering>
        <requestLimits maxAllowedContentLength="10747904" />
      </requestFiltering>
    </security>
    <rewrite>
      <rules>
        <rule name="$($s.Name) no machine API" stopProcessing="true">
          <match url="^api(/|$)" />
          <action type="CustomResponse" statusCode="404" statusReason="Not Found" statusDescription="Not available here" />
        </rule>
        <rule name="$($s.Name) own origin" stopProcessing="true">
          <match url="(.*)" />
          <conditions>
            <add input="{HTTP_ORIGIN}" pattern="$originPattern" />
          </conditions>
          <serverVariables>
            <set name="HTTP_X_FORWARDED_HOST" value="$($s.Internal)" />
            <set name="HTTP_ORIGIN" value="https://$($s.Internal)" />
          </serverVariables>
          <action type="Rewrite" url="$Desk{UNENCODED_URL}" appendQueryString="false" />
        </rule>
        <rule name="$($s.Name) to the desk" stopProcessing="true">
          <match url="(.*)" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_HOST" value="$($s.Internal)" />
          </serverVariables>
          <action type="Rewrite" url="$Desk{UNENCODED_URL}" appendQueryString="false" />
        </rule>
      </rules>
      <outboundRules>
        <rule name="$($s.Name) cookie Secure">
          <match serverVariable="RESPONSE_Set_Cookie" pattern="^(.+)$" />
          <conditions>
            <add input="{R:1}" pattern=";\s*Secure\s*(;|$)" negate="true" />
          </conditions>
          <action type="Rewrite" value="{R:1}; Secure" />
        </rule>
      </outboundRules>
    </rewrite>
  </system.webServer>
</configuration>
"@
}

foreach ($s in $Sites) {
    $exists = [bool](Get-Website -Name $s.Name -ErrorAction SilentlyContinue)
    $binding = '127.0.0.1:{0}:{1}' -f $s.Port, $s.Public
    if (-not $Apply) {
        "PREVIEW  $($s.Name): http $binding -> $Desk as $($s.Internal); folder $($s.Path); " +
            $(if ($exists) { 'site EXISTS, would be left as it is' } else { 'would be created' })
        continue
    }
    if ($exists) { "SKIP     $($s.Name): already exists, left as it is"; continue }
    if (-not (Test-Path $s.Path)) { New-Item -ItemType Directory -Path $s.Path | Out-Null }
    [IO.File]::WriteAllText((Join-Path $s.Path 'web.config'), (Get-WebConfigText $s), (New-Object Text.UTF8Encoding($false)))
    if (-not (Test-Path ("IIS:\AppPools\" + $s.Name))) {
        New-WebAppPool -Name $s.Name | Out-Null
        Set-ItemProperty ("IIS:\AppPools\" + $s.Name) -Name managedRuntimeVersion -Value ''
    }
    New-Website -Name $s.Name -PhysicalPath $s.Path -ApplicationPool $s.Name `
        -IPAddress '127.0.0.1' -Port $s.Port -HostHeader $s.Public | Out-Null
    foreach ($v in 'HTTP_X_FORWARDED_HOST', 'HTTP_ORIGIN') {
        Add-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Location $s.Name `
            -Filter 'system.webServer/rewrite/allowedServerVariables' -Name '.' -Value @{ name = $v }
    }
    "MADE     $($s.Name): http $binding -> $Desk as $($s.Internal)"
}
if (-not $Apply) { 'Nothing was changed. Re-run with -Apply.' }
