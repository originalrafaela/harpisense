param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._-]*$')]
    [string]$SshAlias,
    [ValidateRange(1024, 65535)]
    [int]$LocalPort = 18000
)

# Manual operator action only. Does not edit SSH config, known_hosts, VM services or firewall.
$ErrorActionPreference = 'Stop'
if (Get-NetTCPConnection -State Listen -LocalPort $LocalPort -ErrorAction SilentlyContinue) {
    throw "A porta local $LocalPort está ocupada. Confira o processo antes de continuar."
}
$forward = '127.0.0.1:{0}:127.0.0.1:8000' -f $LocalPort
& ssh.exe -N -T -o ExitOnForwardFailure=yes -o GatewayPorts=no -o ServerAliveInterval=30 -o StrictHostKeyChecking=yes -L $forward $SshAlias
if ($LASTEXITCODE -ne 0) {
    throw 'O túnel SSH não foi estabelecido. Confira alias, chave e fingerprint conhecidos; não compartilhe credenciais.'
}
