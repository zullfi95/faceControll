# SSH Connection Diagnostic Script (Local Windows Check)
# Use this script on Windows to check connection to server

param(
    [string]$ServerIP = "46.63.223.55",
    [int]$Port = 22
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "SSH CONNECTION DIAGNOSTIC (LOCAL)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. SERVER AVAILABILITY CHECK:" -ForegroundColor Yellow
$pingResult = Test-Connection -ComputerName $ServerIP -Count 2 -Quiet
if ($pingResult) {
    Write-Host "   [OK] Server is reachable (ping)" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] Server is NOT reachable (ping)" -ForegroundColor Red
    Write-Host "   Check internet connection and server IP address" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "2. SSH PORT CHECK ($Port):" -ForegroundColor Yellow
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($ServerIP, $Port, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)
    if ($wait) {
        $tcpClient.EndConnect($connect)
        Write-Host "   [OK] Port $Port is open and accessible" -ForegroundColor Green
        $tcpClient.Close()
    } else {
        Write-Host "   [FAIL] Port $Port is not accessible (timeout)" -ForegroundColor Red
        Write-Host "   Possible reasons:" -ForegroundColor Yellow
        Write-Host "   - Firewall on server blocks port $Port" -ForegroundColor Yellow
        Write-Host "   - Hetzner panel firewall blocks port $Port" -ForegroundColor Yellow
        Write-Host "   - SSH service is not running on server" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [FAIL] Port $Port is not accessible: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    if ($tcpClient) {
        $tcpClient.Close()
    }
}
Write-Host ""

Write-Host "3. SSH CLIENT CHECK:" -ForegroundColor Yellow
$sshPath = Get-Command ssh -ErrorAction SilentlyContinue
if ($sshPath) {
    Write-Host "   [OK] SSH client is installed" -ForegroundColor Green
    Write-Host "   Path: $($sshPath.Source)" -ForegroundColor Gray
    $sshVersion = ssh -V 2>&1
    Write-Host "   Version: $sshVersion" -ForegroundColor Gray
} else {
    Write-Host "   [FAIL] SSH client not found" -ForegroundColor Red
    Write-Host "   Install OpenSSH or use PuTTY" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "4. CONNECTION TEST:" -ForegroundColor Yellow
Write-Host "   Attempting connection to $ServerIP :$Port ..." -ForegroundColor Gray
Write-Host "   (This may take a few seconds)" -ForegroundColor Gray
Write-Host ""

$testConnection = Test-NetConnection -ComputerName $ServerIP -Port $Port -WarningAction SilentlyContinue
if ($testConnection.TcpTestSucceeded) {
    Write-Host "   [OK] Connection successful!" -ForegroundColor Green
    Write-Host "   You can connect via SSH" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] Connection failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "   RECOMMENDATIONS:" -ForegroundColor Yellow
    Write-Host "   1. Access server via Hetzner console" -ForegroundColor White
    Write-Host "   2. Run on server: bash scripts/diagnose-ssh.sh" -ForegroundColor White
    Write-Host "   3. Check firewall in Hetzner panel (port $Port must be open)" -ForegroundColor White
    Write-Host "   4. On server run: ufw allow $Port/tcp" -ForegroundColor White
    Write-Host "   5. On server run: systemctl start sshd" -ForegroundColor White
}
Write-Host ""

Write-Host "5. CONNECTION INSTRUCTIONS:" -ForegroundColor Yellow
Write-Host "   To connect use:" -ForegroundColor White
Write-Host "   ssh root@$ServerIP" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Or with port:" -ForegroundColor White
Write-Host "   ssh -p $Port root@$ServerIP" -ForegroundColor Cyan
Write-Host ""

Write-Host "6. ADDITIONAL DIAGNOSTICS:" -ForegroundColor Yellow
Write-Host "   If connection doesn't work, run on SERVER:" -ForegroundColor White
Write-Host "   - bash scripts/diagnose-ssh.sh" -ForegroundColor Cyan
Write-Host "   - bash scripts/check-server.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "   See documentation: docs/SSH_TROUBLESHOOTING.md" -ForegroundColor Gray
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "DIAGNOSTIC COMPLETE" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
