#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
VENV_PYTHON="$VENV/bin/python"
DATA_DIR="${CRD_NOTES_DATA_DIR:-$ROOT/data}"
CONFIG_PATH="$DATA_DIR/config.json"

write_banner() {
  printf '\n'
  printf '   ______ ____   ____        _   ______  ____________ _____\n'
  printf '  / ____// __ \\ / __ \\      / | / / __ \\/_  __/ ____// ___/\n'
  printf ' / /    / /_/ // / / /_____/  |/ / / / / / / / __/   \\__ \\ \n'
  printf '/ /___ / _, _// /_/ //____/ /|  / /_/ / / / / /___  ___/ / \n'
  printf '\\____//_/ |_|/_____/     /_/ |_/\\____/ /_/ /_____/ /____/  \n'
  printf '\n'
  printf '  crd-notes starter - Martin Di Donna\n'
  printf '\n'
}

write_step() {
  printf '  > %s\n' "$1"
}

write_info() {
  printf '    %s\n' "$1"
}

find_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

test_python() {
  [[ -x "$1" ]] && "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

new_project_venv() {
  write_step "Creo l'ambiente virtuale Python."
  local python_cmd
  python_cmd="$(find_python)" || {
    printf 'Python 3.10 o superiore non trovato.\n' >&2
    exit 1
  }
  write_info "Runtime selezionato: $python_cmd"
  "$python_cmd" -m venv "$VENV" --clear
}

new_crd_initial_config() {
  if [[ -f "$CONFIG_PATH" ]]; then
    write_step "Config esistente trovata: mantengo i preset gia' salvati."
    return
  fi

  local python_cmd
  python_cmd="$(find_python)" || {
    printf 'Python 3.10 o superiore non trovato.\n' >&2
    exit 1
  }

  write_step "Primo avvio: rilevo CPU/GPU e preparo preset locali."
  mkdir -p "$DATA_DIR"
  local config_report
  config_report="$(CRD_CONFIG_PATH="$CONFIG_PATH" "$python_cmd" - <<'PY'
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def run(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
    except Exception:
        return ""


def cpu_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    value = run(["lscpu"])
    for line in value.splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def memory_gb() -> int:
    system = platform.system()
    if system == "Darwin":
        value = run(["sysctl", "-n", "hw.memsize"])
        return round(int(value) / (1024**3)) if value.isdigit() else 0
    if Path("/proc/meminfo").exists():
        for line in Path("/proc/meminfo").read_text(errors="ignore").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / (1024**2))
    return 0


def physical_cores(logical_processors: int) -> int:
    system = platform.system()
    if system == "Darwin":
        value = run(["sysctl", "-n", "hw.physicalcpu"])
        return int(value) if value.isdigit() else logical_processors
    output = run(["lscpu", "-p=Core,Socket"])
    if output:
        cores = {
            line.strip()
            for line in output.splitlines()
            if line.strip() and not line.startswith("#")
        }
        if cores:
            return len(cores)
    return logical_processors


def gpu_info() -> tuple[list[str], bool, str, int]:
    names: list[str] = []
    cuda_available = False
    cuda_gpu = ""
    cuda_memory_mb = 0

    if shutil.which("nvidia-smi"):
        output = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if output:
            first = output.splitlines()[0]
            parts = [part.strip() for part in first.split(",", 1)]
            cuda_available = True
            cuda_gpu = parts[0]
            names.append(cuda_gpu)
            if len(parts) > 1 and parts[1].isdigit():
                cuda_memory_mb = int(parts[1])

    system = platform.system()
    if system == "Darwin":
        output = run(["system_profiler", "SPDisplaysDataType"])
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Chipset Model:"):
                names.append(stripped.split(":", 1)[1].strip())
    elif shutil.which("lspci"):
        output = run(["lspci"])
        for line in output.splitlines():
            lowered = line.lower()
            if "vga compatible controller" in lowered or "3d controller" in lowered:
                names.append(line.split(":", 2)[-1].strip())

    deduped = list(dict.fromkeys(name for name in names if name))
    return deduped, cuda_available, cuda_gpu, cuda_memory_mb


def preset_for(hardware: dict[str, object]) -> dict[str, object]:
    logical = int(hardware["logical_processors"])
    memory = int(hardware["memory_gb"])
    cuda = bool(hardware["cuda_available"])
    cuda_memory = int(hardware["cuda_memory_mb"])
    threads = max(1, min(64, logical - 1))
    has_ollama = shutil.which("ollama") is not None

    if cuda and cuda_memory >= 10000 and memory >= 24:
        return {
            "name": "gpu-performance",
            "whisper_model": "medium",
            "whisper_device": "cuda",
            "whisper_compute_type": "float16",
            "whisper_cpu_threads": max(1, min(8, threads // 2)),
            "whisper_workers": 2,
            "rag_chunk_size_words": 220,
            "rag_chunk_overlap_words": 45,
            "rag_top_k": 10,
            "rag_candidate_k": 48,
            "rag_max_context_chars": 4800,
            "rag_rerank_enabled": True,
            "ai_model": "qwen2.5:14b",
            "ollama_enabled": has_ollama,
        }

    if (cuda and cuda_memory >= 6000) or memory >= 16 or logical >= 8:
        return {
            "name": "balanced",
            "whisper_model": "small",
            "whisper_device": "cuda" if cuda else "cpu",
            "whisper_compute_type": "float16" if cuda else "int8",
            "whisper_cpu_threads": threads,
            "whisper_workers": 1,
            "rag_chunk_size_words": 180,
            "rag_chunk_overlap_words": 35,
            "rag_top_k": 8,
            "rag_candidate_k": 32,
            "rag_max_context_chars": 3200,
            "rag_rerank_enabled": True,
            "ai_model": "llama3.1:8b",
            "ollama_enabled": has_ollama,
        }

    return {
        "name": "cpu-light",
        "whisper_model": "base",
        "whisper_device": "cpu",
        "whisper_compute_type": "int8",
        "whisper_cpu_threads": threads,
        "whisper_workers": 1,
        "rag_chunk_size_words": 140,
        "rag_chunk_overlap_words": 25,
        "rag_top_k": 5,
        "rag_candidate_k": 16,
        "rag_max_context_chars": 2200,
        "rag_rerank_enabled": False,
        "ai_model": "phi3:mini",
        "ollama_enabled": has_ollama,
    }


logical_processors = os.cpu_count() or 1
gpu_names, cuda_available, cuda_gpu, cuda_memory_mb = gpu_info()
hardware = {
    "cpu_name": cpu_name(),
    "logical_processors": logical_processors,
    "physical_cores": physical_cores(logical_processors),
    "memory_gb": memory_gb(),
    "gpu_names": gpu_names,
    "cuda_available": cuda_available,
    "cuda_gpu": cuda_gpu,
    "cuda_memory_mb": cuda_memory_mb,
}
preset = preset_for(hardware)
settings = {
    "hardware_preset": preset["name"],
    "detected_hardware": hardware,
    "whisper_model": preset["whisper_model"],
    "transcription_language": "it",
    "whisper_device": preset["whisper_device"],
    "whisper_compute_type": preset["whisper_compute_type"],
    "whisper_beam_size": 1,
    "whisper_cpu_threads": preset["whisper_cpu_threads"],
    "whisper_workers": preset["whisper_workers"],
    "whisper_vad_filter": True,
    "whisper_condition_on_previous_text": False,
    "active_provider": "ollama",
    "active_prompt": "riunione_tecnica",
    "rag": {
        "enabled": True,
        "storage_dir": "rag",
        "collection_prefix": "workspace",
        "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "chunk_size_words": preset["rag_chunk_size_words"],
        "chunk_overlap_words": preset["rag_chunk_overlap_words"],
        "top_k": preset["rag_top_k"],
        "candidate_k": preset["rag_candidate_k"],
        "max_context_chars": preset["rag_max_context_chars"],
        "rerank_enabled": preset["rag_rerank_enabled"],
        "rerank_model": "cross-encoder/ms-marco-MiniLM-L6-v2",
        "hybrid_keyword_enabled": True,
        "enrich_summaries": True,
        "enrich_with_transcript_chunks": True,
        "enrich_with_summary_chunks": True,
        "enrich_with_metadata_chunks": True,
        "enrich_with_operation_chunks": True,
        "enrich_with_knowledge_chunks": True,
    },
    "providers": {
        "openai": {"enabled": False, "api_key": "", "base_url": "https://api.openai.com/v1", "model": ""},
        "openrouter": {"enabled": False, "api_key": "", "base_url": "https://openrouter.ai/api/v1", "model": ""},
        "ollama": {
            "enabled": preset["ollama_enabled"],
            "api_key": "",
            "base_url": "http://127.0.0.1:11434",
            "model": preset["ai_model"],
        },
        "lmstudio": {"enabled": False, "api_key": "", "base_url": "http://127.0.0.1:1234/v1", "model": ""},
        "copilot": {"enabled": False, "api_key": "", "base_url": "", "model": ""},
    },
}

config_path = Path(os.environ["CRD_CONFIG_PATH"])
config_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
gpu_summary = "; ".join(hardware["gpu_names"]) if hardware["gpu_names"] else "nessuna GPU dedicata rilevata"
cuda_summary = (
    f"CUDA disponibile su {hardware['cuda_gpu']} ({hardware['cuda_memory_mb']} MB)"
    if hardware["cuda_available"]
    else "CUDA non disponibile"
)
print(f"CPU: {hardware['cpu_name']}")
print(f"Core/logical processor: {hardware['physical_cores']}/{hardware['logical_processors']}, RAM: {hardware['memory_gb']} GB")
print(f"GPU: {gpu_summary}")
print(cuda_summary)
print(f"Preset: {preset['name']}")
print(
    "Whisper: modello {whisper_model}, device {whisper_device}, compute {whisper_compute_type}, "
    "thread CPU {whisper_cpu_threads}, worker {whisper_workers}".format(**preset)
)
print(
    "RAG: chunk {rag_chunk_size_words}/overlap {rag_chunk_overlap_words}, top_k {rag_top_k}, "
    "candidati {rag_candidate_k}, rerank {rag_rerank_enabled}".format(**preset)
)
print(
    "AI locale: Ollama {status}, modello default {ai_model}".format(
        status="rilevato" if preset["ollama_enabled"] else "non rilevato",
        **preset,
    )
)
print(f"Preset '{preset['name']}' salvato in {config_path}.")
PY
)"
  while IFS= read -r line; do
    write_info "$line"
  done <<< "$config_report"
}

write_banner
write_info "Root progetto: $ROOT"
write_info "Directory dati: $DATA_DIR"
write_info "Config: $CONFIG_PATH"
new_crd_initial_config

if ! test_python "$VENV_PYTHON"; then
  new_project_venv
else
  write_step "Ambiente virtuale Python trovato."
  write_info "$("$VENV_PYTHON" --version)"
fi

if [[ "${CRD_NOTES_SKIP_DEPS:-}" =~ ^(1|true|yes)$ ]]; then
  write_step "CRD_NOTES_SKIP_DEPS attivo: salto aggiornamento dipendenze."
else
  write_step "Aggiorno pip."
  "$VENV_PYTHON" -m pip install --upgrade pip

  write_step "Installo o aggiorno le dipendenze Python."
  write_info "Requirements: $ROOT/requirements.txt"
  "$VENV_PYTHON" -m pip install -r "$ROOT/requirements.txt"
fi

if [[ "${CRD_NOTES_SKIP_FRONTEND:-}" =~ ^(1|true|yes)$ ]]; then
  write_step "CRD_NOTES_SKIP_FRONTEND attivo: salto dipendenze Node e build frontend."
elif command -v npm >/dev/null 2>&1 && [[ -f "$ROOT/package.json" ]]; then
  write_step "Installo o aggiorno le dipendenze Node opzionali."
  write_info "NPM: $(npm --version)"
  (cd "$ROOT" && npm install)
  write_step "Compilo il nuovo frontend modulare."
  (cd "$ROOT" && npm run frontend:build)
else
  write_step "Node/NPM non trovato: salto bridge Copilot opzionale e build frontend."
fi

HOST_NAME="${CRD_NOTES_HOST:-127.0.0.1}"
PORT="${CRD_NOTES_PORT:-8184}"

write_step "Avvio crd-notes su http://${HOST_NAME}:${PORT}"
printf '\n'
cd "$ROOT"
exec "$VENV_PYTHON" "$ROOT/main.py"
