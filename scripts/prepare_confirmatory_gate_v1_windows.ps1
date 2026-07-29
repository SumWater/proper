param(
    [switch]$DownloadPublicTest
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$targetDirectory = Join-Path $repoRoot "work\toolmisusebench_test"
$targetFile = Join-Path $targetDirectory "test_public.jsonl"
$expectedHash = "12c5e1e93926f4089dfc8d0c60cea53b556057360562375510744858fc6f1161"
$expectedBytes = 1695141
$revision = "98eb28718b0393e029088ce80604c48807216de4"
$url = "https://huggingface.co/datasets/sigdelakshey/ToolMisuseBench/resolve/$revision/data/v0_2_large/test_public.jsonl"

if ($DownloadPublicTest) {
    New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
    $temporaryFile = Join-Path $targetDirectory "test_public.jsonl.download"
    Invoke-WebRequest -Uri $url -OutFile $temporaryFile
    $temporaryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporaryFile).Hash.ToLower()
    $temporaryBytes = (Get-Item -LiteralPath $temporaryFile).Length
    if ($temporaryHash -ne $expectedHash -or $temporaryBytes -ne $expectedBytes) {
        throw "Downloaded public-test identity mismatch; refusing to install it."
    }
    Move-Item -Force -LiteralPath $temporaryFile -Destination $targetFile
}

if (-not (Test-Path -LiteralPath $targetFile -PathType Leaf)) {
    throw "Public test is absent. Re-run with -DownloadPublicTest after reviewing the frozen protocol."
}
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetFile).Hash.ToLower()
$actualBytes = (Get-Item -LiteralPath $targetFile).Length
if ($actualHash -ne $expectedHash -or $actualBytes -ne $expectedBytes) {
    throw "Existing public-test identity mismatch."
}

python experiments\proper_v1\confirmatory_gate_v1.py --prepare
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments\proper_v1\confirmatory_gate_v1.py --cpu-dry-run
exit $LASTEXITCODE
