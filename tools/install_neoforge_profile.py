#!/usr/bin/env python3
"""Instala o NeoForge numa pasta isolada (instalacao 'client' numa pasta vazia),
migra as bibliotecas e o JSON da versao para o .minecraft oficial e registra
o perfil do launcher apontando para essa versao.

O installer do NeoForge nao pode ser executado direto em .minecraft (ele se
recusa por seguranca), entao usamos uma pasta scratch e movemos o resultado.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MC = Path(os.environ["APPDATA"]) / ".minecraft"
INST_ID = "aetheron-reino-caido"
INSTANCE = MC / "modpacks" / INST_ID
PROFILE_NAME = "Aetheron: O Reino Caido"
JAVA = MC / "runtime" / "java-runtime-delta" / "windows-x64" / "java-runtime-delta" / "bin" / "java.exe"


def current_neoforge() -> str:
    for line in (ROOT / "pack.toml").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("neoforge"):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("neoforge nao encontrado no pack.toml")


def run_installer(neoforge: str) -> Path:
    installer = MC / "installer-cache" / f"neoforge-installer-{neoforge}.jar"
    if not installer.exists():
        raise SystemExit(f"Installer ausente: {installer} (rode build_instance.py)")
    java = JAVA if JAVA.exists() else Path("java")
    scratch = Path(tempfile.mkdtemp(prefix="nf-install-"))
    # O installer exige um perfil de launcher na pasta alvo
    (scratch / "launcher_profiles.json").write_text(
        json.dumps({"profiles": {}, "settings": {}, "version": 3}), encoding="utf-8")
    print(f"Rodando installer do NeoForge {neoforge} em {scratch} ...")
    cmd = [str(java), "-jar", str(installer), "--installClient", str(scratch)]
    proc = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:])
        raise SystemExit(f"Installer falhou (codigo {proc.returncode})")
    version_dir = scratch / "versions" / f"neoforge-{neoforge}"
    if not version_dir.exists():
        raise SystemExit(f"Versao nao gerada em {version_dir}")
    return scratch


def migrate(scratch: Path, neoforge: str) -> str:
    # Bibliotecas
    src_lib = scratch / "libraries"
    if src_lib.exists():
        shutil.copytree(src_lib, MC / "libraries", dirs_exist_ok=True)
    ver = f"neoforge-{neoforge}"
    src_ver = scratch / "versions" / ver
    dst_ver = MC / "versions" / ver
    dst_ver.mkdir(parents=True, exist_ok=True)
    for f in src_ver.iterdir():
        shutil.copy2(f, dst_ver / f.name)
    return ver


def register(version_id: str) -> str:
    prof_path = MC / "launcher_profiles.json"
    data = json.loads(prof_path.read_text(encoding="utf-8"))
    profiles = data.setdefault("profiles", {})
    pid = None
    for k, v in profiles.items():
        if v.get("gameDir") and Path(v["gameDir"]).name == INST_ID:
            pid = k
            break
    if pid is None:
        import random
        pid = "aetheron" + "".join(random.choice("0123456789abcdef") for _ in range(27))
        profiles[pid] = {"type": "custom", "created": "2026-11-25T00:00:00.000Z", "icon": "Dirt"}
    profiles[pid].update({
        "name": PROFILE_NAME,
        "gameDir": str(INSTANCE),
        "lastVersionId": version_id,
        "javaArgs": "-Xmx12G -Xms4G -XX:+UseG1GC -XX:+ParallelRefProcEnabled -Dfile.encoding=UTF-8",
    })
    data["selectedProfile"] = pid
    prof_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return pid


def main() -> int:
    neoforge = current_neoforge()
    scratch = run_installer(neoforge)
    version_id = migrate(scratch, neoforge)
    shutil.rmtree(scratch, ignore_errors=True)
    pid = register(version_id)
    print(f"\nVersao instalada : {version_id}")
    print(f"Perfil do launcher: {PROFILE_NAME} ({pid})")
    print(f"Pasta do jogo    : {INSTANCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
