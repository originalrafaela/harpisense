"""Build the pure Python reader wheel offline using only the standard library."""
import base64
import csv
import hashlib
import io
from pathlib import Path
import sys
import zipfile


def build(destination):
    root = Path(__file__).resolve().parent
    version = '1.0.0'
    name = 'harpisense_xai_reader'
    dist = name+'-'+version+'.dist-info'
    files = {'xai_api/'+p.name:p.read_bytes().replace(b'\r\n',b'\n') for p in root.glob('*.py')
             if p.name not in ('build_wheel.py',)}
    files[dist+'/METADATA'] = ('Metadata-Version: 2.1\nName: harpisense-xai-reader\nVersion: '+version+
        '\nSummary: Read-only canonical HarpiSense XAI adapter\nRequires-Python: >=3.12\n\n').encode()
    files[dist+'/WHEEL'] = b'Wheel-Version: 1.0\nGenerator: harpisense-offline-reader-build\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    records = io.StringIO(newline='')
    writer = csv.writer(records, lineterminator='\n')
    for path, blob in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
        writer.writerow([path,'sha256='+digest,len(blob)])
    writer.writerow([dist+'/RECORD','',''])
    files[dist+'/RECORD'] = records.getvalue().encode()
    destination = Path(destination); destination.mkdir(parents=True,exist_ok=True)
    wheel = destination/(name+'-'+version+'-py3-none-any.whl')
    with zipfile.ZipFile(wheel,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path,blob in sorted(files.items()):
            info = zipfile.ZipInfo(path,date_time=(2026,11,7,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,blob)
    print(wheel.name+' sha256='+hashlib.sha256(wheel.read_bytes()).hexdigest())


if __name__=='__main__':
    build(sys.argv[1])
