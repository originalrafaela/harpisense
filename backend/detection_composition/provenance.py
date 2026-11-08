"""Record byte provenance and verify the single canonical domain against P09 V2."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', required=True)
    args = parser.parse_args()
    references = Path(args.references)
    package = references/'versão_v2/09_Deteccao_Decisao/HarpiSense_Pacote09_Deteccao_Decisao_v2'
    root = Path(__file__).resolve().parents[2]
    hashes = {}
    for name in ('harpisense_data', 'harpisense_rf', 'harpisense_if', 'harpisense_xai'):
        for source in sorted((package/name).rglob('*.py')):
            relative = source.relative_to(package)
            installed = root/'backend/domain'/relative
            if installed.read_bytes() != source.read_bytes():
                raise ValueError('Vendored source differs: '+str(relative))
            hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    canonical = []
    for relative in [Path('harpisense_catalog.py'),
                     *[p.relative_to(package) for name in ('harpisense_contracts', 'harpisense_engines')
                       for p in (package/name).rglob('*.py')]]:
        installed = root/'backend/domain'/relative
        # Existing canonical copy may have normalized line endings, but no AST divergence.
        actual = ast.parse(installed.read_text(encoding='utf-8-sig'))
        expected = ast.parse((package/relative).read_text(encoding='utf-8-sig'))
        if relative == Path('harpisense_catalog.py'):
            # Preserve the already integrated, user-authorized M2 correction.
            overrides = dict(CATALOG_VERSION="'harpisense.catalog.v2.2026-10-27'",
                AUTONOMY="{1:{'Low':'MANUAL','Medium':'MANUAL','Hard':'MANUAL'},"
                         "2:{'Low':'AUTO','Medium':'MANUAL','Hard':'MANUAL'},"
                         "3:{'Low':'AUTO','Medium':'AUTO','Hard':'AUTO'}}")
            for node in expected.body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    if name in overrides:
                        node.value = ast.parse(overrides[name], mode='eval').body
        if ast.dump(actual) != ast.dump(expected):
            raise ValueError('Canonical domain differs: '+str(relative))
        canonical.append(str(relative))
    loose = [str(p.relative_to(references)) for extension in ('*.joblib', '*.pkl', '*.pickle', '*.onnx')
             for p in references.rglob(extension)]
    archived = []
    for archive in references.rglob('*.zip'):
        with zipfile.ZipFile(archive) as stream:
            archived.extend(str(archive.relative_to(references))+'!'+name for name in stream.namelist()
                            if name.lower().endswith(('.joblib', '.pkl', '.pickle', '.onnx')))
    manifest = dict(reference=str(package.relative_to(references)), sha256=hashes,
                    canonical_ast_equal=sorted(canonical), loose_model_artifacts=loose,
                    archived_model_artifacts=archived,
                    p08_source_commit='c314ca5282fe282dc6455e83d74e949c98fa4676',
                    preserved_catalog_override='Existing v2.2026-10-27: M2 Medium requires approval')
    destination = root/'backend/detection_composition/ORIGINS.json'
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(vendored_files=len(hashes), canonical_files=len(canonical),
                          loose_artifacts=loose, archived_artifacts=archived), ensure_ascii=False))


if __name__ == '__main__':
    main()
