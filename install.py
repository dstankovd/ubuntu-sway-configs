#!/usr/bin/env python3
"""Link managed configuration into HOME, preserving replaced paths in a backup."""

import argparse
from datetime import datetime
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / 'home'
    home = args.home.expanduser().resolve()
    backup = home / '.local/state/ubuntu-sway-configs/backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')

    # Link application directories so atomic config-file saves stay in the repo.
    # Keep shared directories (systemd, Pictures, .local/share) independently owned.
    paths = [Path('.bashrc'), Path('.local/share/easyeffects')]
    paths += [p.relative_to(root) for p in sorted((root / '.config').iterdir())
              if p.name != 'systemd']
    paths += [p.relative_to(root) for p in sorted((root / '.config/systemd/user').iterdir())]
    paths += [p.relative_to(root) for p in sorted((root / 'Pictures/Wallpapers').iterdir())]

    changed = 0
    for rel in paths:
        source, target = root / rel, home / rel
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if not source.exists():
            raise FileNotFoundError(source)
        print(f'{target} -> {source}')
        if args.dry_run:
            continue
        if target.exists() or target.is_symlink():
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(saved))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=source.is_dir())
        changed += 1
    if changed:
        print(f'Linked {changed} paths. Backups: {backup}')
    elif not args.dry_run:
        print('All managed paths are already linked.')


if __name__ == '__main__':
    main()
