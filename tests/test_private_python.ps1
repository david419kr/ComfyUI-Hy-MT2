param(
    [Parameter(Mandatory=$true)][string]$HostPython,
    [Parameter(Mandatory=$true)][string]$Uv,
    [string]$TestRoot = (Join-Path $env:TEMP ('HyMT2 no-link test ' + [Guid]::NewGuid().ToString('N')))
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$source = Join-Path (Split-Path -Parent $PSScriptRoot) 'install-comfyui-hymt2.ps1'
$tokens=$null; $errors=$null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if ($errors) { throw 'Installer syntax is invalid.' }
foreach ($function in $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $false)) {
    Invoke-Expression $function.Extent.Text
}
foreach ($statement in $ast.EndBlock.Statements) {
    if ($statement -is [System.Management.Automation.Language.AssignmentStatementAst] -and $statement.Left.VariablePath.UserPath -in @('pythonUrl','pythonHash')) {
        Invoke-Expression $statement.Extent.Text
    }
}
$PortableRoot = [IO.Path]::GetFullPath($TestRoot)
$uv = [IO.Path]::GetFullPath($Uv)
$node = Join-Path $PortableRoot 'ComfyUI/custom_nodes/ComfyUI-Hy-MT2'
if (Test-Path -LiteralPath $node) { throw 'Test root must not contain an existing node.' }
$tools = Join-Path $PortableRoot '.hymt2-tools'
New-Item -ItemType Directory -Path $node,$tools -Force | Out-Null
$oldInstallDir = [Environment]::GetEnvironmentVariable('UV_PYTHON_INSTALL_DIR')
$oldDownloads = [Environment]::GetEnvironmentVariable('UV_PYTHON_DOWNLOADS')
try {
    Remove-Item Env:UV_PYTHON_INSTALL_DIR -ErrorAction SilentlyContinue
    $env:UV_PYTHON_DOWNLOADS = 'never'
    $python = Private-Python $node $HostPython $tools
    $venv = Join-Path $node '.venv'
    Run-UV -Arguments @('venv','--no-managed-python','--no-python-downloads','--python',$python,'--relocatable','--link-mode','copy',$venv)
    & (Join-Path $venv 'Scripts/python.exe') -I -c 'import sys; assert sys.version_info[:2] == (3, 13)'
    if ($LASTEXITCODE -ne 0) { throw 'Private venv cannot start.' }
    $links = @(Get-ChildItem -LiteralPath (Join-Path $node '.python'),$venv -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if ($links.Count) { throw 'Fresh Python/venv unexpectedly contains links.' }
    Write-Host 'PASS: archive Python and venv use ordinary files/directories, no links.'

    $fresh = Checked-Path (Join-Path $node '.python/python')
    $legacy = Checked-Path (Join-Path $node '.python/cpython-3.13.12-windows-x86_64-none')
    Move-Item -LiteralPath $fresh -Destination $legacy
    function Download([string]$Url, [string]$File) { throw 'Partial-install recovery unexpectedly tried to download Python.' }
    $recovered = Private-Python $node $HostPython $tools
    if ($recovered -ne (Join-Path $legacy 'python.exe')) { throw 'Failed to reuse the extracted patch-version Python.' }
    Run-UV -Arguments @('venv','--no-managed-python','--no-python-downloads','--python',$recovered,'--relocatable','--link-mode','copy',(Join-Path $node '.venv-recovered'))
    & (Join-Path $node '.venv-recovered/Scripts/python.exe') -I -c 'import sys; assert sys.version_info[:2] == (3, 13)'
    if ($LASTEXITCODE -ne 0) { throw 'Recovered private venv cannot start.' }
    $links = @(Get-ChildItem -LiteralPath (Join-Path $node '.python'),(Join-Path $node '.venv-recovered') -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if ($links.Count) { throw 'Recovery unexpectedly created a link.' }
    Write-Host 'PASS: failed-install patch Python is reused without download or minor-version links.'
} finally {
    [Environment]::SetEnvironmentVariable('UV_PYTHON_INSTALL_DIR',$oldInstallDir)
    [Environment]::SetEnvironmentVariable('UV_PYTHON_DOWNLOADS',$oldDownloads)
}
