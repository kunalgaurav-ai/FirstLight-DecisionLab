"""Protect complete inherited releases and v5.5 additions by SHA-256."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent

def check():
    from firstlight_v541.verify import verify
    inherited=verify()
    manifest=json.loads((ROOT/'FIRST_LIGHT_V55_SOURCE_SHA256.json').read_text())
    if manifest.get('inherited_release')!='v5.4.1':raise ValueError('BAD_INHERITED_RELEASE')
    for name,digest in manifest['sha256_by_path'].items():
        file=(ROOT/name).resolve()
        if not file.is_relative_to(ROOT.resolve()) or not file.is_file():raise ValueError('MISSING_RELEASE_ITEM:'+name)
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:raise ValueError('SOURCE_INTEGRITY_ERROR:'+name)
    return {'inherited_count':inherited,'v55_items':len(manifest['sha256_by_path'])}

if __name__=='__main__':print('FIRST LIGHT v5.5 SOURCE INTEGRITY:',check())
