"""Publica as tabelas finais de `metrics/` (sem caches) para uma pasta de destino.

O Colab grava em `Drive/Sprinklers/metrics/`. Este script copia so as tabelas finais (pastas Parquet e
`_runs`) para o disco do backend, ou para uma pasta que depois se sincroniza com um bucket (rclone/aws s3 sync).
Ignora `_partial_*`, `_l2_parts`, `*.tmp`, `*.old` e ficheiros soltos de logs antigos.

    python data/pipeline/scripts/publish_metrics.py /content/drive/MyDrive/Sprinklers/metrics data/metrics
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SKIP_PREFIXES = ("_partial", "_l2_parts")
SKIP_SUFFIXES = (".tmp", ".old")


def is_published_table(path: Path) -> bool:
    name = path.name
    return (path.is_dir() and not name.startswith(SKIP_PREFIXES) and not name.endswith(SKIP_SUFFIXES))


def publish(source, dest) -> list[str]:
    """Copia cada tabela final de `source` para `dest/<nome>/`, substituindo a anterior de forma
    segura (copia para `<nome>.tmp` e troca). Devolve os nomes publicados, ordenados.
    Levanta FileNotFoundError se `source` nao existir e ValueError se nao houver tabelas."""
    source, dest = Path(source), Path(dest)
    if not source.is_dir():
        raise FileNotFoundError(f"pasta de origem inexistente: {source}")
    tables = sorted(p for p in source.iterdir() if is_published_table(p))
    if not tables:
        raise ValueError(f"nenhuma tabela final em {source}")
    dest.mkdir(parents=True, exist_ok=True)
    for src in tables:
        tmp, final, old = dest / f"{src.name}.tmp", dest / src.name, dest / f"{src.name}.old"
        for leftover in (tmp, old):
            if leftover.exists():
                shutil.rmtree(leftover)
        shutil.copytree(src, tmp)
        if final.exists():
            final.replace(old)
        tmp.replace(final)
        if old.exists():
            shutil.rmtree(old)
    return [p.name for p in tables]


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(__doc__)
        return 2
    names = publish(*args)
    print(f"{len(names)} tabelas publicadas em {args[1]}: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
