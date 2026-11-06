"""Provision a separate Ubuntu cloud-image VM; never reuse an existing test disk."""
import argparse
import hashlib
import io
import json
import re
import shutil
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.native-test/seed-tools'))
import pycdlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

parser = argparse.ArgumentParser()
parser.add_argument('--target-name', default='candidate2-clean-20261106')
parser.add_argument('--hostname', default='harpisense-candidate2-clean')
parser.add_argument('--image-file', type=Path)
parser.add_argument('--checksum-file', type=Path)
args = parser.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', args.target_name):
    raise SystemExit('INVALID_TARGET_NAME')
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', args.hostname):
    raise SystemExit('INVALID_HOSTNAME')
if bool(args.image_file) != bool(args.checksum_file):
    raise SystemExit('CACHED_IMAGE_REQUIRES_CHECKSUM_FILE')
target = ROOT/'.native-test'/args.target_name
target.mkdir(parents=True, exist_ok=False)
base = 'https://cloud-images.ubuntu.com/noble/20261017/'
image = 'noble-server-cloudimg-amd64.vmdk'
checksums = (args.checksum_file.read_text() if args.checksum_file else
             urllib.request.urlopen(base + 'SHA256SUMS').read().decode())
expected = next(line.split()[0] for line in checksums.splitlines() if line.endswith(image))
(target/'SHA256SUMS').write_text(checksums)
if args.image_file:
    print('Verifying cached official Ubuntu 24.04 image', flush=True)
    shutil.copyfile(args.image_file, target/image)
else:
    print('Downloading official Ubuntu 24.04 image', flush=True)
    urllib.request.urlretrieve(base + image, target/image)
actual = hashlib.file_digest((target/image).open('rb'), 'sha256').hexdigest()
if actual != expected:
    raise SystemExit('CLOUD_IMAGE_CHECKSUM_MISMATCH')
print('CLOUD_IMAGE_SHA256_OK', flush=True)
key = Ed25519PrivateKey.generate()
(target/'trial_ed25519').write_bytes(key.private_bytes(serialization.Encoding.PEM,
    serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))
public = key.public_key().public_bytes(serialization.Encoding.OpenSSH,
    serialization.PublicFormat.OpenSSH).decode()
(target/'trial_ed25519.pub').write_text(public + '\n')
userdata = f'''#cloud-config
hostname: {args.hostname}
manage_etc_hosts: true
ssh_pwauth: false
users:
  - name: trial
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - {public}
packages: [open-vm-tools]
'''
iso = pycdlib.PyCdlib()
iso.new(interchange_level=3, joliet=3, vol_ident='cidata')
for name, data in [('user-data', userdata), ('meta-data',
    f'instance-id: {args.target_name}\nlocal-hostname: {args.hostname}\n')]:
    blob = data.encode()
    iso.add_fp(io.BytesIO(blob), len(blob), iso_path='/' + name.upper().replace('-', '_') + ';1',
               joliet_path='/' + name)
iso.write(str(target/'seed.iso'))
iso.close()
tools = Path('C:/Program Files (x86)/VMware/VMware Workstation')
subprocess.run([str(tools/'vmware-vdiskmanager.exe'), '-r', str(target/image), '-t', '0',
                str(target/'system.vmdk')], check=True)
subprocess.run([str(tools/'vmware-vdiskmanager.exe'), '-x', '24GB', str(target/'system.vmdk')], check=True)
template = ROOT/'.native-test/clean-os/ubuntu2404/HarpiSense-Clean.vmx'
lines = template.read_text().splitlines()
allowed = ('config.version', 'virtualHW.version', 'pciBridge', 'guestOS', 'firmware',
           'numvcpus', 'scsi0.', 'ethernet0.present', 'ethernet0.connectionType',
           'ethernet0.virtualDev', 'ethernet0.pciSlotNumber', 'ethernet0.addressType')
config = [line for line in lines if line.startswith(allowed)]
config += ['.encoding = "UTF-8"', f'displayName = "HarpiSense {args.hostname}"',
    'memsize = "2048"', 'scsi0:0.present = "TRUE"', 'scsi0:0.fileName = "system.vmdk"',
    'sata0.present = "TRUE"', 'sata0.pciSlotNumber = "36"', 'sata0:0.present = "TRUE"',
    'sata0:0.deviceType = "cdrom-image"', 'sata0:0.fileName = "seed.iso"',
    'sata0:0.startConnected = "TRUE"', 'serial0.present = "TRUE"',
    'serial0.fileType = "file"', 'serial0.fileName = "console.log"',
    'isolation.tools.hgfs.disable = "TRUE"', 'sharedFolder.maxNum = "0"']
(target/'Candidate2-Clean.vmx').write_text('\n'.join(config) + '\n')
(target/'origin.json').write_text(json.dumps({'source': base+image, 'sha256': actual,
    'new_disk': True, 'ram_mib': 2048}, indent=2))
print('NEW_CLEAN_VM_PREPARED:' + str(target/'Candidate2-Clean.vmx'))
