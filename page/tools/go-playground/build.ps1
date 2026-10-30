$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$assetRoot = Join-Path $repositoryRoot 'page/static/golang-runtime'
$cacheRoot = Join-Path $repositoryRoot '.deps/go-playground'
$environmentNames = @('GOTOOLCHAIN', 'GOMODCACHE', 'GOCACHE', 'GOPATH', 'GOOS', 'GOARCH')
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    New-Item -ItemType Directory -Path $assetRoot, $cacheRoot -Force | Out-Null
    $env:GOTOOLCHAIN = 'go1.22.12'
    $env:GOMODCACHE = Join-Path $cacheRoot 'modules'
    $env:GOCACHE = Join-Path $cacheRoot 'build'
    $env:GOPATH = Join-Path $cacheRoot 'gopath'
    Push-Location $PSScriptRoot
    try {
        go mod download all
        if ($LASTEXITCODE -ne 0) { throw '下載 Go Playground 依賴失敗。' }
        $toolchainRoot = go env GOROOT
        if ($LASTEXITCODE -ne 0) { throw '無法讀取 Go toolchain 路徑。' }
        $env:GOOS = 'js'
        $env:GOARCH = 'wasm'
        $wasmBuild = Join-Path $cacheRoot 'golang.wasm'
        go build -trimpath -ldflags='-s -w' -o $wasmBuild .
        if ($LASTEXITCODE -ne 0) { throw '建置 Go Playground WebAssembly 失敗。' }
        $wasmSource = [IO.File]::OpenRead($wasmBuild)
        $compressedFile = [IO.File]::Create((Join-Path $assetRoot 'golang.wasm.gz'))
        $gzip = [IO.Compression.GZipStream]::new($compressedFile, [IO.Compression.CompressionMode]::Compress)
        try { $wasmSource.CopyTo($gzip) } finally {
            $gzip.Dispose()
            $compressedFile.Dispose()
            $wasmSource.Dispose()
        }
        $runtimeSource = Join-Path $toolchainRoot 'misc/wasm/wasm_exec.js'
        $runtimeTarget = Join-Path $assetRoot 'wasm_exec.js'
        if (Test-Path -LiteralPath $runtimeSource) {
            Copy-Item -LiteralPath $runtimeSource -Destination $runtimeTarget -Force
        } elseif (-not (Test-Path -LiteralPath $runtimeTarget)) {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/golang/go/go1.22.12/misc/wasm/wasm_exec.js' -OutFile $runtimeTarget
        }
        $expectedRuntimeHash = '45CE9DFE7211247544AB6F4268EB8CB5B6F3D5AE602DC3B51447B7EADA99C229'
        if ((Get-FileHash -LiteralPath $runtimeTarget -Algorithm SHA256).Hash -ne $expectedRuntimeHash) {
            throw 'wasm_exec.js 與固定的 Go 1.22.12 版本不符。'
        }
        Copy-Item -LiteralPath (Join-Path $toolchainRoot 'LICENSE') -Destination (Join-Path $assetRoot 'GO-LICENSE.txt') -Force
        Copy-Item -LiteralPath (Join-Path $env:GOMODCACHE 'github.com/traefik/yaegi@v0.16.1/LICENSE') -Destination (Join-Path $assetRoot 'YAEGI-LICENSE.txt') -Force
        Get-Item (Join-Path $assetRoot 'golang.wasm.gz') | Select-Object Name, Length
    } finally {
        Pop-Location
    }
} finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
