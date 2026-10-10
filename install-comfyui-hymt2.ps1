# SPDX-License-Identifier: MIT
param([Alias('ComfyRoot')][string]$PortableRoot = '')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$fork = 'https://github.com/david419kr/ComfyUI-Hy-MT2'
$uvVersion = '0.10.11'
$uvHash = '9ee74df98582f37fdd6069e1caac80d2616f9a489f5dbb2b1c152f30be69c58e'

function Download([string]$Url, [string]$File) {
    Invoke-WebRequest -Uri $Url -OutFile $File -UseBasicParsing -Headers @{'User-Agent'='ComfyUI-Hy-MT2-installer'}
}
function Checked-Path([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (!$full.StartsWith($script:PortableRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside the portable installation: $full"
    }
    $parent = $full
    while ($parent) {
        if ((Test-Path -LiteralPath $parent) -and ((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Managed runtime paths must not be junctions or symbolic links: $parent"
        }
        if ($parent -eq $script:PortableRoot) { break }
        $parent = Split-Path -Parent $parent
    }
    return $full
}
function Run-UV([string[]]$Arguments) {
    & $script:uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv failed: $($Arguments -join ' ')" }
}

try {
    if (![Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'This installer requires 64-bit Windows PowerShell on Windows x64.'
    }
    $candidates = if ($PortableRoot) { @($PortableRoot) } else { @($PSScriptRoot, (Get-Location).Path) }
    $found = $null
    foreach ($candidate in $candidates) {
        $candidate = [IO.Path]::GetFullPath($candidate)
        if ((Test-Path -LiteralPath (Join-Path $candidate 'main.py')) -and (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $candidate) 'python_embeded/python.exe'))) {
            $candidate = Split-Path -Parent $candidate
        }
        if ((Test-Path -LiteralPath (Join-Path $candidate 'ComfyUI/main.py')) -and (Test-Path -LiteralPath (Join-Path $candidate 'python_embeded/python.exe'))) {
            $found = $candidate
            break
        }
    }
    if (!$found) { throw 'Put both installer files inside ComfyUI_windows_portable, or pass -PortableRoot <folder>.' }
    $PortableRoot = if ($found -eq [IO.Path]::GetPathRoot($found)) { $found } else { $found.TrimEnd('\') }
    $comfy = Join-Path $PortableRoot 'ComfyUI'
    $hostPython = Join-Path $PortableRoot 'python_embeded/python.exe'
    Write-Host "Portable root: $PortableRoot"
    Write-Host 'Close ComfyUI before installing or updating this node.'
    & $hostPython -I -c 'import torch'
    if ($LASTEXITCODE -ne 0) { throw 'The portable ComfyUI Python cannot import torch. Repair the base ComfyUI installation first.' }

    $tools = Checked-Path (Join-Path $PortableRoot '.hymt2-tools')
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
    $uv = Join-Path $tools 'uv.exe'
    if (!(Test-Path -LiteralPath $uv)) {
        $zip = Join-Path $tools 'uv.zip'
        Download "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" $zip
        if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $uvHash) { throw 'uv download checksum mismatch.' }
        Expand-Archive -LiteralPath $zip -DestinationPath $tools -Force
        if (!(Test-Path -LiteralPath $uv)) { throw 'uv.exe was not found in the downloaded archive.' }
        Remove-Item -LiteralPath $zip
    }

    $nodes = Checked-Path (Join-Path $comfy 'custom_nodes')
    New-Item -ItemType Directory -Path $nodes -Force | Out-Null
    $node = Checked-Path (Join-Path $nodes 'ComfyUI-Hy-MT2')
    $git = Get-Command git -ErrorAction SilentlyContinue
    $update = $false
    if ((Test-Path -LiteralPath (Join-Path $node '.git')) -and $git) {
        $origin = & $git.Source -C $node remote get-url origin 2>$null
        if ($LASTEXITCODE -eq 0 -and $origin.TrimEnd('/').Replace('.git','') -eq $fork) {
            $dirty = & $git.Source -C $node status --porcelain
            if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'The fork has local source changes; commit or back them up before updating.' }
            $branch = & $git.Source -C $node branch --show-current
            if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') { throw 'The installed fork must be on main to update automatically.' }
            & $git.Source -C $node pull --ff-only origin main
            if ($LASTEXITCODE -ne 0) { throw 'Fork update failed; existing files were preserved.' }
            $update = $true
        }
    }
    if (!$update) {
        $stage = Checked-Path (Join-Path $tools ('node-' + [Guid]::NewGuid().ToString('N')))
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        if ($git) {
            $source = Join-Path $stage 'source'
            & $git.Source clone ($fork + '.git') $source
            if ($LASTEXITCODE -ne 0) { throw 'Hy-MT2 fork download failed.' }
        } else {
            $archive = Join-Path $stage 'node.zip'
            Download ($fork + '/archive/refs/heads/main.zip') $archive
            Expand-Archive -LiteralPath $archive -DestinationPath $stage
            $source = Join-Path $stage 'ComfyUI-Hy-MT2-main'
        }
        if (!(Test-Path -LiteralPath (Join-Path $source 'runtime/llama_worker.py'))) { throw 'Downloaded fork is missing its private runtime.' }
        $backup = $null
        if (Test-Path -LiteralPath $node) {
            $backups = Checked-Path (Join-Path $PortableRoot '.hymt2-backups')
            New-Item -ItemType Directory -Path $backups -Force | Out-Null
            $backup = Checked-Path (Join-Path $backups ('ComfyUI-Hy-MT2-' + [Guid]::NewGuid().ToString('N')))
            Move-Item -LiteralPath $node -Destination $backup
            Write-Host "Previous node backed up: $backup"
        }
        try {
            $source = Checked-Path $source
            Move-Item -LiteralPath $source -Destination $node
        } catch {
            if ($backup -and !(Test-Path -LiteralPath $node)) { Move-Item -LiteralPath $backup -Destination $node }
            throw
        }
        if ($backup -and (Test-Path -LiteralPath (Join-Path $backup '.venv'))) {
            $oldEnv = Checked-Path (Join-Path $backup '.venv')
            $newEnv = Checked-Path (Join-Path $node '.venv')
            Move-Item -LiteralPath $oldEnv -Destination $newEnv
        }
    }

    $oldPythonDir = [Environment]::GetEnvironmentVariable('UV_PYTHON_INSTALL_DIR')
    $oldDownloads = [Environment]::GetEnvironmentVariable('UV_PYTHON_DOWNLOADS')
    try {
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $node '.python'
        $env:UV_PYTHON_DOWNLOADS = 'automatic'
        Run-UV -Arguments @('python','install','--no-bin','3.13')
        $venv = Checked-Path (Join-Path $node '.venv')
        $python = Join-Path $venv 'Scripts/python.exe'
        $validEnv = $false
        if (Test-Path -LiteralPath $python) {
            & $python -I -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)'
            $validEnv = $LASTEXITCODE -eq 0
        }
        if (!$validEnv) {
            if (Test-Path -LiteralPath $venv) {
                $oldEnv = Checked-Path (Join-Path $node ('.venv.backup-' + [Guid]::NewGuid().ToString('N')))
                Move-Item -LiteralPath $venv -Destination $oldEnv
            }
            Run-UV -Arguments @('venv','--managed-python','--python','3.13','--relocatable',$venv)
        }
        Run-UV -Arguments @('pip','install','--python',$python,'--only-binary',':all:','--link-mode','copy','--requirements',(Join-Path $node 'runtime/requirements.txt'))
        & $hostPython -I -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('huggingface_hub') else 1)"
        if ($LASTEXITCODE -ne 0) { Run-UV -Arguments @('pip','install','--python',$hostPython,'--system','--only-binary',':all:','huggingface-hub') }
        & $python -I -X utf8 (Join-Path $node 'runtime/llama_worker.py') --check
        if ($LASTEXITCODE -ne 0) { throw 'Private runtime validation failed. Check the NVIDIA driver and messages above, then rerun this installer.' }
    } finally {
        [Environment]::SetEnvironmentVariable('UV_PYTHON_INSTALL_DIR', $oldPythonDir)
        [Environment]::SetEnvironmentVariable('UV_PYTHON_DOWNLOADS', $oldDownloads)
    }
    Write-Host "Hy-MT2 fork installed: $node"
    Write-Host "Private Python/CUDA runtime: $venv"
    Write-Host 'Restart ComfyUI. GGUF files belong in ComfyUI/models/LLM/GGUF.'
} catch {
    Write-Host ("Installation failed: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
