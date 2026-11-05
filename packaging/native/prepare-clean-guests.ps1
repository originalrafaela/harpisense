[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$WindowsIso,
    [Parameter(Mandatory)][string]$UbuntuIso,
    [ValidateSet('None','Windows','Ubuntu')][string]$StartPlatform = 'None',
    [ValidateRange(1024,8192)][int]$HostReserveMiB = 2048
)
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$testRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.native-test/clean-os'))
if (-not $testRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Test directory must remain inside this worktree.'
}
$vmwareDirectory = 'C:/Program Files (x86)/VMware/VMware Workstation'
$diskManager = Join-Path $vmwareDirectory 'vmware-vdiskmanager.exe'
$vmrun = Join-Path $vmwareDirectory 'vmrun.exe'
foreach ($path in @($WindowsIso, $UbuntuIso, $diskManager, $vmrun)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing input: $path" }
}
$targets = @(
    @{Platform='Windows'; Id='windows11'; Guest='windows11-64'; Iso=$WindowsIso},
    @{Platform='Ubuntu'; Id='ubuntu2404'; Guest='ubuntu-64'; Iso=$UbuntuIso}
)
foreach ($target in $targets) {
    $directory = Join-Path $testRoot $target.Id
    $vmx = Join-Path $directory 'HarpiSense-Clean.vmx'
    $disk = Join-Path $directory 'system.vmdk'
    if (Test-Path -LiteralPath $directory) {
        if (-not (Test-Path -LiteralPath $vmx) -or -not (Test-Path -LiteralPath $disk)) {
            throw "Incomplete existing target preserved: $directory"
        }
        continue
    }
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    & $diskManager -c -s 64GB -a lsilogic -t 0 $disk
    if ($LASTEXITCODE -ne 0) { throw 'Sparse disk creation failed; partial target preserved.' }
    $iso = (Resolve-Path -LiteralPath $target.Iso).Path.Replace('\','/')
    $config = @"
.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "21"
pciBridge0.present = "TRUE"
pciBridge0.pciSlotNumber = "17"
pciBridge4.present = "TRUE"
pciBridge4.virtualDev = "pcieRootPort"
pciBridge4.functions = "8"
pciBridge4.pciSlotNumber = "21"
pciBridge5.present = "TRUE"
pciBridge5.virtualDev = "pcieRootPort"
pciBridge5.functions = "8"
pciBridge5.pciSlotNumber = "22"
pciBridge6.present = "TRUE"
pciBridge6.virtualDev = "pcieRootPort"
pciBridge6.functions = "8"
pciBridge6.pciSlotNumber = "23"
pciBridge7.present = "TRUE"
pciBridge7.virtualDev = "pcieRootPort"
pciBridge7.functions = "8"
pciBridge7.pciSlotNumber = "24"
displayName = "HarpiSense native $($target.Platform) CLEAN TEST"
guestOS = "$($target.Guest)"
firmware = "efi"
memsize = "4096"
numvcpus = "2"
scsi0.present = "TRUE"
scsi0.virtualDev = "lsilogic"
scsi0.pciSlotNumber = "16"
scsi0:0.present = "TRUE"
scsi0:0.fileName = "system.vmdk"
sata0.present = "TRUE"
sata0.pciSlotNumber = "36"
sata0:0.present = "TRUE"
sata0:0.deviceType = "cdrom-image"
sata0:0.fileName = "$iso"
sata0:0.startConnected = "TRUE"
ethernet0.present = "TRUE"
ethernet0.connectionType = "nat"
ethernet0.virtualDev = "e1000e"
ethernet0.pciSlotNumber = "160"
ethernet0.addressType = "generated"
usb.present = "FALSE"
sound.present = "FALSE"
isolation.tools.hgfs.disable = "TRUE"
sharedFolder.maxNum = "0"
"@
    [IO.File]::WriteAllText($vmx, $config, [Text.UTF8Encoding]::new($false))
}
if ($StartPlatform -ne 'None') {
    $freeMb = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024
    # Default reserve 2 GiB; an explicit 1 GiB reserve permits one guest on a quieter host.
    $requiredMb = 4096 + $HostReserveMiB
    if ($freeMb -lt $requiredMb) {
        throw ('CLEAN_GUEST_START_BLOCKED: free RAM {0:N0} MiB; need {1} MiB. Lab preserved.' -f $freeMb,$requiredMb)
    }
    $target = $targets | Where-Object { $_.Platform -eq $StartPlatform }
    $vmx = Join-Path (Join-Path $testRoot $target.Id) 'HarpiSense-Clean.vmx'
    & $vmrun start $vmx nogui
    if ($LASTEXITCODE -ne 0) { throw 'Guest startup failed; existing lab VMs were not changed.' }
}
$targets | ForEach-Object {
    [pscustomobject]@{
        Platform=$_.Platform
        Vmx=(Join-Path (Join-Path $testRoot $_.Id) 'HarpiSense-Clean.vmx')
        State='fresh_sparse_disk_os_not_installed'
        MemoryMiB=4096
    }
} | ConvertTo-Json
