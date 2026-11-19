from pathlib import Path
import argparse
import hashlib
import json
import sys

root = Path(__file__).resolve().parent.parent
PROJECT_SUPER = 'images/super.img'
FIRMWARE_INPUTS = {PROJECT_SUPER, 'rollback/super.img'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(package_root=root, source_only=False, *, stock_only=False):
    if source_only and stock_only:
        raise ValueError('Choose either source or stock verification')
    manifest = json.loads((package_root / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    required = {'images/super.img', 'images/vbmeta.img', 'rollback/super.img', 'rollback/vbmeta.img'}
    if not required <= manifest.keys():
        raise ValueError('Manifest omits required firmware files')
    checked = 0
    for name, expected in manifest.items():
        path = (package_root / name).resolve()
        if not path.is_relative_to(package_root.resolve()):
            raise ValueError('Manifest path escapes package: ' + name)
        if (source_only and name in FIRMWARE_INPUTS) or (stock_only and name == PROJECT_SUPER):
            continue
        if not path.is_file():
            raise FileNotFoundError(f'Missing packaged file: {name}. See docs/BUILD_AND_RELEASE.md; source checkouts are not flash packages.')
        if digest(path) != expected:
            raise ValueError('Hash mismatch: ' + name)
        checked += 1
    return checked


def verify_readback(package_root=root, original=False):
    manifest = json.loads((package_root / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    folder = 'rollback' if original else 'images'
    for name in ('super.img', 'vbmeta.img'):
        actual = package_root / 'readback' / name
        target = package_root / folder / name
        if actual.stat().st_size != target.stat().st_size:
            raise ValueError(name + ': size mismatch')
        # Compare against the release hash, not a possibly changed local image.
        if digest(actual) != manifest[f'{folder}/{name}']:
            raise ValueError(name + ': SHA256 mismatch')
        print('PASS readback: ' + name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--source', action='store_true', help='Check source checkout; never authorizes flashing')
    mode.add_argument('--stock', action='store_true', help='Check stock recovery files offline; skip only the project super image')
    mode.add_argument('--readback', nargs='?', const='clean', choices=['clean', 'original'])
    args = parser.parse_args()
    try:
        if args.readback:
            verify_readback(original=args.readback == 'original')
        else:
            count = verify(source_only=args.source, stock_only=args.stock)
            label = ('SOURCE ONLY (not flashable)' if args.source else
                     'STOCK FILES (offline)' if args.stock else 'PACKAGE')
            print(f'PASS {label}: {count} files verified by SHA256.')
    except Exception as error:
        print('STOP: ' + str(error))
        sys.exit(1)
