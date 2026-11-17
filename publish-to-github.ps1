# Run in PowerShell from the extracted Stone Growth OS project directory.
# Requires git and GitHub HTTPS authentication.
param([string]$RemoteUrl = 'https://github.com/slotmagia/stone-seo-growth.git')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is not installed.' }
if (Test-Path .git) { throw 'Local .git already exists. Inspect before publishing.' }
if (-not ((Test-Path pyproject.toml) -and (Test-Path app) -and (Test-Path docs))) { throw 'Project files are missing.' }
$refs = & git ls-remote $RemoteUrl
if ($LASTEXITCODE -ne 0) { throw 'Cannot read remote. Verify network and access.' }
if ($refs) { throw 'Remote has commits/refs. Refusing to overwrite existing history.' }
& git init -b main
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
& git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
& git commit -m 'feat: initialize Stone Growth OS SEO/GEO MVP v0.1.0'
if ($LASTEXITCODE -ne 0) { throw 'git commit failed. Configure git user.name and user.email.' }
& git remote add origin $RemoteUrl
if ($LASTEXITCODE -ne 0) { throw 'git remote add failed' }
& git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'git push failed. Verify write access and authentication.' }
Write-Host "Published: $RemoteUrl (main)"
