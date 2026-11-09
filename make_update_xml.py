"""Write the update XML the vendor updater reads (element name 'Verison' is the vendor's spelling).

usage: make_update_xml.py <apk> <version> <download_url> <out.xml>
"""
import hashlib
import sys
from pathlib import Path

apk, version, url, out = sys.argv[1:5]
data = Path(apk).read_bytes()

xml = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<update>\n"
    "  <Verison>\n"
    "    <name>WirelessRemote</name>\n"
    f"    <version>{version}</version>\n"
    f"    <path>{url}</path>\n"
    f"    <md5>{hashlib.md5(data).hexdigest()}</md5>\n"
    f"    <size>{len(data)}</size>\n"
    "    <info>Works on phones without an IR blaster;Updates come from GitHub;</info>\n"
    "  </Verison>\n"
    "</update>\n"
)
Path(out).write_text(xml, encoding="utf-8")
print(xml)
