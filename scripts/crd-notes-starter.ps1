$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$DataDir = if ($env:CRD_NOTES_DATA_DIR) { $env:CRD_NOTES_DATA_DIR } else { Join-Path $Root "data" }
$ConfigPath = Join-Path $DataDir "config.json"

function Write-Banner {
    Write-Host ""
    Write-Host "   ______ ____   ____        _   ______  ____________ _____" -ForegroundColor Magenta
    Write-Host "  / ____// __ \ / __ \      / | / / __ \/_  __/ ____// ___/" -ForegroundColor Magenta
    Write-Host " / /    / /_/ // / / /_____/  |/ / / / / / / / __/   \__ \ " -ForegroundColor Magenta
    Write-Host "/ /___ / _, _// /_/ //____/ /|  / /_/ / / / / /___  ___/ / " -ForegroundColor Magenta
    Write-Host "\____//_/ |_|/_____/     /_/ |_/\____/ /_/ /_____/ /____/  " -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  crd-notes starter - Martin Di Donna" -ForegroundColor DarkMagenta
    Write-Host ""
}

function Write-Step {
    param([string] $Message)
    Write-Host "  > $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string] $Message)
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Test-Python {
    param([string] $PythonPath)
    if (-not (Test-Path $PythonPath)) {
        return $false
    }
    & $PythonPath -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Get-CompatiblePython {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) {
        py -3.10 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Command = "py"; Arguments = @("-3.10") }
        }
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Command = "py"; Arguments = @("-3") }
        }
    }

    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($Python) {
        & $Python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Command = $Python.Source; Arguments = @() }
        }
    }

    return $null
}

function New-ProjectVenv {
    Write-Step "Creo l'ambiente virtuale Python."
    $PythonCommand = Get-CompatiblePython
    if ($PythonCommand) {
        Write-Info "Runtime selezionato: $($PythonCommand.Command) $($PythonCommand.Arguments -join ' ')"
        & $PythonCommand.Command @($PythonCommand.Arguments) -m venv $Venv --clear
        if ($LASTEXITCODE -eq 0) { return }
    }

    throw "Python 3.10 o superiore non trovato."
}

function Test-CrdFfmpegWasapi {
    $Ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $Ffmpeg) {
        return [pscustomobject]@{
            available = $false
            path = ""
            wasapi = $false
        }
    }

    $HelpOutput = & $Ffmpeg.Source -hide_banner -h demuxer=wasapi 2>&1
    $LoopbackAvailable = $LASTEXITCODE -eq 0 -and (($HelpOutput | Out-String) -match "(^|\s)-loopback(\s|$)")
    return [pscustomobject]@{
        available = $true
        path = $Ffmpeg.Source
        wasapi = $LoopbackAvailable
    }
}

function Install-CrdFfmpegWithWinget {
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $Winget) {
        Write-Info "winget non disponibile: installa ffmpeg manualmente e riavvia lo starter."
        return
    }

    Write-Step "Installo ffmpeg (pacchetto winget: Gyan.FFmpeg)."
    & $Winget.Source install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Installazione automatica ffmpeg non riuscita. Procedi manualmente e riavvia lo starter."
    }
}

function Get-CrdHardwareInfo {
    $Cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue
    $System = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
    $GpuControllers = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
    $LogicalProcessors = [int](($Cpu | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum)
    $PhysicalCores = [int](($Cpu | Measure-Object -Property NumberOfCores -Sum).Sum)
    if ($LogicalProcessors -le 0) {
        $LogicalProcessors = [Environment]::ProcessorCount
    }
    if ($PhysicalCores -le 0) {
        $PhysicalCores = $LogicalProcessors
    }
    $MemoryGb = if ($System.TotalPhysicalMemory) { [math]::Round($System.TotalPhysicalMemory / 1GB) } else { 0 }
    $GpuNames = @($GpuControllers | ForEach-Object { $_.Name } | Where-Object { $_ })
    $CudaAvailable = $false
    $CudaName = ""
    $CudaMemoryMb = 0
    $NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($NvidiaSmi) {
        $NvidiaOutput = & $NvidiaSmi.Source --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $NvidiaOutput) {
            $FirstGpu = @($NvidiaOutput)[0]
            $Parts = $FirstGpu -split ","
            $CudaAvailable = $true
            $CudaName = $Parts[0].Trim()
            if ($Parts.Count -gt 1) {
                [void][int]::TryParse($Parts[1].Trim(), [ref]$CudaMemoryMb)
            }
        }
    }

    [pscustomobject]@{
        cpu_name = @($Cpu | Select-Object -First 1 -ExpandProperty Name)
        logical_processors = $LogicalProcessors
        physical_cores = $PhysicalCores
        memory_gb = $MemoryGb
        gpu_names = $GpuNames
        cuda_available = $CudaAvailable
        cuda_gpu = $CudaName
        cuda_memory_mb = $CudaMemoryMb
    }
}

function Write-CrdHardwareSummary {
    param([pscustomobject] $Hardware)
    $GpuSummary = if ($Hardware.gpu_names -and $Hardware.gpu_names.Count -gt 0) { $Hardware.gpu_names -join "; " } else { "nessuna GPU dedicata rilevata" }
    $CudaSummary = if ($Hardware.cuda_available) { "CUDA disponibile su $($Hardware.cuda_gpu) ($($Hardware.cuda_memory_mb) MB)" } else { "CUDA non disponibile" }
    Write-Info "CPU: $($Hardware.cpu_name)"
    Write-Info "Core/logical processor: $($Hardware.physical_cores)/$($Hardware.logical_processors), RAM: $($Hardware.memory_gb) GB"
    Write-Info "GPU: $GpuSummary"
    Write-Info $CudaSummary
}

function Write-CrdPresetSummary {
    param([pscustomobject] $Preset)
    Write-Info "Preset: $($Preset.name)"
    Write-Info "Whisper: modello $($Preset.whisper_model), device $($Preset.whisper_device), compute $($Preset.whisper_compute_type), thread CPU $($Preset.whisper_cpu_threads), worker $($Preset.whisper_workers)"
    Write-Info "RAG: chunk $($Preset.rag_chunk_size_words)/overlap $($Preset.rag_chunk_overlap_words), top_k $($Preset.rag_top_k), candidati $($Preset.rag_candidate_k), rerank $($Preset.rag_rerank_enabled)"
    Write-Info "AI locale: Ollama $(if ($Preset.ollama_enabled) { 'rilevato' } else { 'non rilevato' }), modello default $($Preset.ai_model)"
}

function Get-CrdPreset {
    param([pscustomobject] $Hardware)
    $Threads = [Math]::Max(1, [Math]::Min(64, $Hardware.logical_processors - 1))
    $Ollama = Get-Command ollama -ErrorAction SilentlyContinue
    $HasOllama = [bool]$Ollama

    if ($Hardware.cuda_available -and $Hardware.cuda_memory_mb -ge 10000 -and $Hardware.memory_gb -ge 24) {
        return [pscustomobject]@{
            name = "gpu-performance"
            whisper_model = "medium"
            whisper_device = "cuda"
            whisper_compute_type = "float16"
            whisper_cpu_threads = [Math]::Max(1, [Math]::Min(8, [Math]::Floor($Threads / 2)))
            whisper_workers = 2
            rag_chunk_size_words = 220
            rag_chunk_overlap_words = 45
            rag_top_k = 10
            rag_candidate_k = 48
            rag_max_context_chars = 4800
            rag_rerank_enabled = $true
            ai_model = "qwen2.5:14b"
            ollama_enabled = $HasOllama
        }
    }

    if (($Hardware.cuda_available -and $Hardware.cuda_memory_mb -ge 6000) -or $Hardware.memory_gb -ge 16 -or $Hardware.logical_processors -ge 8) {
        return [pscustomobject]@{
            name = "balanced"
            whisper_model = "small"
            whisper_device = if ($Hardware.cuda_available) { "cuda" } else { "cpu" }
            whisper_compute_type = if ($Hardware.cuda_available) { "float16" } else { "int8" }
            whisper_cpu_threads = $Threads
            whisper_workers = 1
            rag_chunk_size_words = 180
            rag_chunk_overlap_words = 35
            rag_top_k = 8
            rag_candidate_k = 32
            rag_max_context_chars = 3200
            rag_rerank_enabled = $true
            ai_model = "llama3.1:8b"
            ollama_enabled = $HasOllama
        }
    }

    return [pscustomobject]@{
        name = "cpu-light"
        whisper_model = "base"
        whisper_device = "cpu"
        whisper_compute_type = "int8"
        whisper_cpu_threads = $Threads
        whisper_workers = 1
        rag_chunk_size_words = 140
        rag_chunk_overlap_words = 25
        rag_top_k = 5
        rag_candidate_k = 16
        rag_max_context_chars = 2200
        rag_rerank_enabled = $false
        ai_model = "phi3:mini"
        ollama_enabled = $HasOllama
    }
}

function New-CrdInitialConfig {
    if (Test-Path $ConfigPath) {
        Write-Step "Config esistente trovata: mantengo i preset gia' salvati."
        return
    }

    Write-Step "Primo avvio: rilevo CPU/GPU e preparo preset locali."
    $Hardware = Get-CrdHardwareInfo
    $Preset = Get-CrdPreset $Hardware
    Write-CrdHardwareSummary $Hardware
    Write-CrdPresetSummary $Preset
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    $Settings = [ordered]@{
        hardware_preset = $Preset.name
        detected_hardware = $Hardware
        whisper_model = $Preset.whisper_model
        transcription_language = "it"
        whisper_device = $Preset.whisper_device
        whisper_compute_type = $Preset.whisper_compute_type
        whisper_beam_size = 1
        whisper_cpu_threads = $Preset.whisper_cpu_threads
        whisper_workers = $Preset.whisper_workers
        whisper_vad_filter = $true
        whisper_condition_on_previous_text = $false
        active_provider = "ollama"
        active_prompt = "riunione_tecnica"
        rag = [ordered]@{
            enabled = $true
            storage_dir = "rag"
            collection_prefix = "workspace"
            embedding_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            chunk_size_words = $Preset.rag_chunk_size_words
            chunk_overlap_words = $Preset.rag_chunk_overlap_words
            top_k = $Preset.rag_top_k
            candidate_k = $Preset.rag_candidate_k
            max_context_chars = $Preset.rag_max_context_chars
            rerank_enabled = $Preset.rag_rerank_enabled
            rerank_model = "cross-encoder/ms-marco-MiniLM-L6-v2"
            hybrid_keyword_enabled = $true
            enrich_summaries = $true
            enrich_with_transcript_chunks = $true
            enrich_with_summary_chunks = $true
            enrich_with_metadata_chunks = $true
            enrich_with_operation_chunks = $true
            enrich_with_knowledge_chunks = $true
        }
        providers = [ordered]@{
            openai = [ordered]@{ enabled = $false; api_key = ""; base_url = "https://api.openai.com/v1"; model = "" }
            openrouter = [ordered]@{ enabled = $false; api_key = ""; base_url = "https://openrouter.ai/api/v1"; model = "" }
            ollama = [ordered]@{ enabled = $Preset.ollama_enabled; api_key = ""; base_url = "http://127.0.0.1:11434"; model = $Preset.ai_model }
            lmstudio = [ordered]@{ enabled = $false; api_key = ""; base_url = "http://127.0.0.1:1234/v1"; model = "" }
            copilot = [ordered]@{ enabled = $false; api_key = ""; base_url = ""; model = "" }
        }
    }
    $Settings | ConvertTo-Json -Depth 8 | Set-Content -Path $ConfigPath -Encoding UTF8
    Write-Step "Preset '$($Preset.name)' salvato in $ConfigPath."
}

Write-Banner

Write-Info "Root progetto: $Root"
Write-Info "Directory dati: $DataDir"
Write-Info "Config: $ConfigPath"

New-CrdInitialConfig

$FfmpegProbe = Test-CrdFfmpegWasapi
if (-not $FfmpegProbe.available) {
    Write-Step "ffmpeg non trovato nel PATH di sistema."
    if ($env:CRD_NOTES_INSTALL_FFMPEG -match "^(1|true|yes)$") {
        Install-CrdFfmpegWithWinget
        $FfmpegProbe = Test-CrdFfmpegWasapi
    }
    else {
        Write-Info "Per la registrazione audio Windows e' consigliato ffmpeg con WASAPI loopback."
        Write-Info "Esegui: winget install --id Gyan.FFmpeg --exact"
        Write-Info "Oppure imposta CRD_NOTES_FFMPEG con il path completo di ffmpeg.exe."
    }
}

if ($FfmpegProbe.available -and -not $FfmpegProbe.wasapi) {
    Write-Step "ffmpeg trovato ma senza WASAPI loopback: registrazione audio Windows limitata."
    Write-Info "ffmpeg corrente: $($FfmpegProbe.path)"
    Write-Info "Installa una build completa (es. Gyan.FFmpeg) o abilita Stereo Mix/virtual audio cable."
}
elseif ($FfmpegProbe.available -and $FfmpegProbe.wasapi) {
    Write-Step "ffmpeg compatibile con WASAPI loopback rilevato."
    Write-Info "ffmpeg: $($FfmpegProbe.path)"
}

if (-not (Test-Python $VenvPython)) {
    New-ProjectVenv
}
else {
    Write-Step "Ambiente virtuale Python trovato."
    $PythonVersion = & $VenvPython --version
    Write-Info $PythonVersion
}

if ($env:CRD_NOTES_SKIP_DEPS -match "^(1|true|yes)$") {
    Write-Step "CRD_NOTES_SKIP_DEPS attivo: salto aggiornamento dipendenze."
}
else {
    Write-Step "Aggiorno pip."
    & $VenvPython -m pip install --upgrade pip

    Write-Step "Installo o aggiorno le dipendenze Python."
    Write-Info "Requirements: $(Join-Path $Root "requirements.txt")"
    & $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
}

$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $Npm) {
    $Npm = Get-Command npm -ErrorAction SilentlyContinue
}
if ($env:CRD_NOTES_SKIP_FRONTEND -match "^(1|true|yes)$") {
    Write-Step "CRD_NOTES_SKIP_FRONTEND attivo: salto dipendenze Node e build frontend."
}
elseif ($Npm -and (Test-Path (Join-Path $Root "package.json"))) {
    Write-Step "Installo o aggiorno le dipendenze Node opzionali."
    $NpmVersion = & $Npm.Source --version
    Write-Info "NPM: $NpmVersion"
    Push-Location $Root
    & $Npm.Source install
    Write-Step "Compilo il nuovo frontend modulare."
    & $Npm.Source run frontend:build
    Pop-Location
}
else {
    Write-Step "Node/NPM non trovato: salto bridge Copilot opzionale e build frontend."
}

$HostName = if ($env:CRD_NOTES_HOST) { $env:CRD_NOTES_HOST } else { "127.0.0.1" }
$Port = if ($env:CRD_NOTES_PORT) { $env:CRD_NOTES_PORT } else { "8184" }

Write-Step "Avvio crd-notes su http://${HostName}:$Port"
Write-Host ""
Push-Location $Root
try {
    & $VenvPython (Join-Path $Root "main.py")
}
finally {
    Pop-Location
}
