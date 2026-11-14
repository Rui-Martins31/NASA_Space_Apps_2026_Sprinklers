"""Harness de testes de mutacao do pipeline.

Uso (a partir de qualquer pasta):
    python data/pipeline/scripts/mutate.py MUTANTES.json [--tests tests/test_x.py ...]

MUTANTES.json e uma lista de {"id", "file", "old", "new", "note"}: `file` e relativo a raiz do repo
(ex. "data/pipeline/metrics/cell_recurrence.py") e `old` tem de aparecer exatamente uma vez nele.

O que faz:
1. Copia `data/pipeline/` para uma pasta temporaria que reproduz `<tmp>/data/pipeline/` e inicia nela
   um repo git vazio (alguns testes de notebook correm `git rev-parse HEAD` e procuram o notebook
   relativamente a raiz do repo). Os ficheiros do repo real nunca sao alterados.
2. Corre primeiro a copia SEM mutacao e exige que passe (senao todos os mutantes pareceriam "mortos").
3. Aplica cada mutante, corre os testes e classifica:
     KILLED    pelo menos um teste falhou por asserção (AssertionError / "DID NOT RAISE")
     RUNTIME   so houve erros de execucao ou de importacao: NAO conta como detetado
     SURVIVED  todos os testes passaram: o teste suite nao detetou o mutante
Sai com codigo 0 so se todos os mutantes forem KILLED.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ASSERTION_TYPES = {"AssertionError", "Failed"}


def run_pytest(workdir: Path, tests: list[str], junit: Path) -> tuple[int, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    res = subprocess.run(cmd, cwd=workdir, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


def failure_types(junit: Path) -> tuple[set[str], int]:
    """(tipos de excecao das falhas, nº de erros de coleta/fixture)."""
    root = ET.parse(junit).getroot()
    types, errors = set(), 0
    for case in root.iter("testcase"):
        for f in case.findall("failure"):
            # o pytest nem sempre preenche `type` (p.ex. asserts com pytest.approx): cai para a mensagem
            types.add(f.get("type") or f.get("message", "").split(":")[0])
        errors += len(case.findall("error"))
    return types, errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mutants", type=Path)
    ap.add_argument("--tests", nargs="*", default=["tests"], help="alvos do pytest, relativos a data/pipeline")
    args = ap.parse_args(argv)
    mutants = json.loads(args.mutants.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="mutate_") as tmp:
        root = Path(tmp)
        shutil.copytree(REPO / "data" / "pipeline", root / "data" / "pipeline",
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        work = root / "data" / "pipeline"
        junit = root / "junit.xml"

        code, out = run_pytest(work, args.tests, junit)
        if code != 0:
            print("BASELINE FALHOU (copia sem mutacao): os resultados dos mutantes nao seriam fiaveis.")
            print(out[-3000:])
            return 2
        print(f"baseline OK: {out.strip().splitlines()[-1]}")

        results = []
        for m in mutants:
            target = root / m["file"]
            original = target.read_text(encoding="utf-8")
            if original.count(m["old"]) != 1:
                results.append((m["id"], "BAD", f"`old` aparece {original.count(m['old'])}x"))
                continue
            if m["old"] == m["new"]:
                results.append((m["id"], "BAD", "old == new"))
                continue
            target.write_text(original.replace(m["old"], m["new"]), encoding="utf-8", newline="")
            try:
                code, out = run_pytest(work, args.tests, junit)
                if code == 0:
                    status, detail = "SURVIVED", ""
                else:
                    types, errors = failure_types(junit) if junit.exists() else (set(), 1)
                    if any(t in ASSERTION_TYPES or t.lstrip().startswith("assert") for t in types):
                        status, detail = "KILLED", ""
                    else:
                        status, detail = "RUNTIME", f"tipos={sorted(types)} erros={errors}"
            finally:
                target.write_text(original, encoding="utf-8", newline="")
            results.append((m["id"], status, detail or m.get("note", "")))

    width = max((len(r[0]) for r in results), default=2)
    for mid, status, detail in results:
        print(f"{status:9} {mid:{width}}  {detail if status != 'KILLED' else ''}")
    killed = sum(r[1] == "KILLED" for r in results)
    print(f"\n{killed}/{len(results)} mutantes detetados por asserção")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
