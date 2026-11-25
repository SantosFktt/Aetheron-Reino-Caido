#!/usr/bin/env python3
"""Cria a instancia do modpack 'Aetheron: O Reino Caido' (NeoForge 1.21.1).

- Baixa todos os mods listados em mods/*.pw.toml (Modrinth/CurseForge)
- Copia config/ (quests FTB em pt_br) e o shader Aetheron
- Baixa o installer do NeoForge e registra um perfil no launcher oficial
"""

import json
import os
import random
import shutil
import sys
import tomllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MC = Path(os.environ["APPDATA"]) / ".minecraft"
INST_ID = "aetheron-reino-caido"
INSTANCE = MC / "modpacks" / INST_ID
PROFILE_NAME = "Aetheron: O Reino Caido"
UA = {"User-Agent": "AetheronPackBuilder/1.0 (SantosFktt)"}


def current_neoforge() -> str:
    text = (ROOT / "pack.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("neoforge"):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("neoforge nao encontrado no pack.toml")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(fetch(url))
    tmp.replace(dest)


def load_toml(p: Path) -> dict:
    with open(p, "rb") as f:
        return tomllib.load(f)


def modrinth_url(meta: dict) -> str:
    dl = meta.get("download", {})
    if dl.get("url"):
        return dl["url"]
    mr = meta["update"]["modrinth"]
    if "version-id" in mr:
        ver = json.loads(fetch(f"https://api.modrinth.com/v2/version/{mr['version-id']}"))
    else:
        ver = json.loads(fetch(
            f"https://api.modrinth.com/v2/project/{mr['mod-id']}/version/{mr['version']}"))
    files = ver["files"]
    for f in files:
        if f.get("primary"):
            return f["url"]
    return files[0]["url"]


def curseforge_url(meta: dict) -> str:
    dl = meta.get("download", {})
    if dl.get("url"):
        return dl["url"]
    fid = int(meta["update"]["curseforge"]["file-id"])
    name = meta["filename"]
    for host in ("https://mediafilez.forgecdn.net/files", "https://edge.forgecdn.net/files"):
        url = f"{host}/{fid // 1000}/{fid % 1000}/{urllib.parse.quote(name)}"
        try:
            req = urllib.request.Request(url, headers=UA, method="HEAD")
            with urllib.request.urlopen(req, timeout=30):
                return url
        except Exception:
            continue
    raise RuntimeError("download CurseForge indisponivel")


def download_mods() -> tuple[int, list[tuple[str, str]]]:
    ok, fail = 0, []
    metas = sorted((ROOT / "mods").glob("*.pw.toml"))
    for i, mp in enumerate(metas, 1):
        meta = load_toml(mp)
        dest = INSTANCE / "mods" / meta["filename"]
        if dest.exists() and dest.stat().st_size > 0:
            ok += 1
            continue
        try:
            upd = meta.get("update", {})
            if "modrinth" in upd:
                url = modrinth_url(meta)
            elif "curseforge" in upd:
                url = curseforge_url(meta)
            else:
                raise RuntimeError("sem fonte de update")
            download(url, dest)
            ok += 1
            print(f"[{i}/{len(metas)}] OK   {meta['filename']}")
        except Exception as e:  # noqa: BLE001
            fail.append((meta["filename"], str(e)))
            print(f"[{i}/{len(metas)}] ERRO {meta['filename']}: {e}")
    return ok, fail


def write_options() -> None:
    opts = INSTANCE / "options.txt"
    values: dict[str, str] = {}
    if opts.exists():
        for line in opts.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                values[k] = v
    values.update({
        "lang": "pt_br",
        "shaderPack": "Aetheron-Modern-Iris-1.20+.zip",
        "enableVsync": "false",
        "narrator": "0",
        "guiScale": "3",
        "particles": "0",
        "vsync": "false",
    })
    values.pop("vsync", None)
    opts.write_text("\n".join(f"{k}:{v}" for k, v in sorted(values.items())) + "\n", encoding="utf-8")


def write_modrinth_index(instance_id: str, force: bool) -> None:
    """Permite que o app do Modrinth (se usado) reconheca a instancia."""
    modlist = INSTANCE / "modrinth.index.json"
    if modlist.exists() and not force:
        return
    files = []
    for mp in sorted((ROOT / "mods").glob("*.pw.toml")):
        meta = load_toml(mp)
        if "modrinth" not in meta.get("update", {}):
            continue
        try:
            url = modrinth_url(meta)
        except Exception:
            continue
        files.append({
            "path": f"mods/{meta['filename']}",
            "hashes": {},
            "env": {"client": "required", "server": "required"},
            "downloads": [url],
            "fileSize": (INSTANCE / "mods" / meta["filename"]).stat().st_size
            if (INSTANCE / "mods" / meta["filename"]).exists() else 0,
        })
    if not files:
        return
    index = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": "1.0.0",
        "name": "Aetheron: O Reino Caido",
        "summary": "Modpack de fantasia medieval epica com historia e quests em portugues",
        "files": files,
        "dependencies": {"minecraft": "1.21.1", "neoforge": current_neoforge()},
    }
    modlist.write_text(json.dumps(index, indent=2), encoding="utf-8")


def register_launcher_profile(version_id: str) -> str:
    prof_path = MC / "launcher_profiles.json"
    data = json.loads(prof_path.read_text(encoding="utf-8"))
    profiles = data.setdefault("profiles", {})
    pid = None
    for k, v in profiles.items():
        if v.get("gameDir") and Path(v["gameDir"]).name == INST_ID:
            pid = k
            break
    if pid is None:
        pid = "aetheron" + "".join(random.choice("0123456789abcdef") for _ in range(27))
        profiles[pid] = {
            "type": "custom",
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "icon": "Dirt",
        }
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
    force = "--force" in sys.argv
    neoforge = current_neoforge()
    print(f"Instancia : {INSTANCE}")
    print(f"NeoForge  : {neoforge}")
    for sub in ("mods", "shaderpacks", "saves", "config"):
        (INSTANCE / sub).mkdir(parents=True, exist_ok=True)

    ok, fail = download_mods()

    cfg_src = ROOT / "config"
    if cfg_src.exists():
        shutil.copytree(cfg_src, INSTANCE / "config", dirs_exist_ok=True)
        print("Configs (quests) copiadas.")

    shaders = [
        Path(os.environ["LOCALAPPDATA"]) / "Temp" / "opencode" / "Aetheron-repo" / "dist" / "Aetheron-Modern-Iris-1.20+.zip",
        MC / "modpacks" / "957c0da2-7669-3982-a88a-c3c3325639a1" / "shaderpacks" / "Aetheron-Modern-Iris-1.20+.zip",
    ]
    for s in shaders:
        if s.exists():
            shutil.copy2(s, INSTANCE / "shaderpacks" / s.name)
            print(f"Shader: {s.name}")
            break

    write_options()

    installer = MC / "installer-cache" / f"neoforge-installer-{neoforge}.jar"
    if force or not installer.exists():
        url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge}/neoforge-{neoforge}-installer.jar"
        print(f"Baixando installer do NeoForge {neoforge} ...")
        download(url, installer)

    write_modrinth_index(INST_ID, force)
    print("\nPerfil do launcher: rode tools\\install_neoforge_profile.py para finalizar")
    print(f"Mods OK: {ok}  falhas: {len(fail)}")
    for name, err in fail:
        print(f"  - {name}: {err}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
