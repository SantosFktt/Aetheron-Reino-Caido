#!/usr/bin/env python3
"""Monta o classpath completo (Vanilla 1.21.1 + NeoForge) e mostra o que falta."""

import json
import os
import sys
from pathlib import Path

MC = Path(os.environ["APPDATA"]) / ".minecraft"
VERSION = "neoforge-21.1.267"
VANILLA = "1.21.1"


def lib_path(lib: dict) -> Path:
    name = lib["name"]
    group, artifact, version, *cls = name.split(":")
    classifier = cls[0] if cls and cls[0] else None
    parts = group.split(".") + [artifact, version]
    fn = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + ".jar"
    return MC / "libraries" / Path(*parts) / fn


def collect(version_id: str, seen: set, out: list, missing: list) -> None:
    vjson = json.loads((MC / "versions" / version_id / f"{version_id}.json").read_text(encoding="utf-8"))
    if vjson.get("inheritsFrom"):
        collect(vjson["inheritsFrom"], seen, out, missing)
    for lib in vjson.get("libraries", []):
        name = lib["name"]
        if name in seen:
            continue
        seen.add(name)
        if any(r.get("action") == "allow" and r.get("os", {}).get("name") not in (None, "windows")
               for r in lib.get("rules", [])):
            continue
        p = lib_path(lib)
        if p.exists():
            out.append(str(p))
        else:
            missing.append(name)


def main() -> int:
    paths, missing = [], []
    collect(VERSION, set(), paths, missing)
    print(f"{len(paths)} jars resolvidos")
    for m in missing:
        print("FALTANDO:", m)
    client = MC / "versions" / VANILLA / f"{VANILLA}.jar"
    if client.exists():
        paths.append(str(client))
    inst = MC / "modpacks" / "aetheron-reino-caido"
    args = [
        "-Xmx8G", "-Xms2G",
        "-Djava.library.path=" + str(MC / "versions" / VERSION / "natives"),
        "-Dfml.earlyprogresswindow=false",
        "-cp", ";".join(paths),
        "cpw.mods.bootstraplauncher.BootstrapLauncher",
        "--username", "Tester", "--version", VERSION,
        "--gameDir", str(inst),
        "--assetsDir", str(MC / "assets"),
        "--assetIndex", "17",
        "--accessToken", "0", "--userType", "legacy",
        "--uuid", "00000000000000000000000000000000",
        "--width", "854", "--height", "480",
    ]
    (Path(__file__).resolve().parent / "args.txt").write_text("\n".join(args), encoding="utf-8")
    print(f"client jar: {'ok' if client.exists() else 'AUSENTE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
