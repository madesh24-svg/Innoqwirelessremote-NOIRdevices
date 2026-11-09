"""Stage 1 patches for a decompiled WirelessRemote.

1. In-app updater: the vendor build fetches its update XML over plain HTTP from a domain the
   vendor no longer supports. Point both addresses at this repo's latest release over HTTPS.
2. MainActivity$18$2.run removes IpList[finalK] on the UI thread after the list may already be
   empty (IndexOutOfBoundsException). Skip the remove when the index is out of range.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])

NEW_URL = "https://github.com/madesh24-svg/Innoqwirelessremote-NOIRdevices/releases/latest/download/WirelessRemote.xml"
OLD_URL = re.compile(r"http://www\.vsindia\.monster/download/[a-z]+/WirelessRemote\.xml")

urls = 0
for f in root.rglob("*.smali"):
    text = f.read_text(encoding="utf-8")
    if "vsindia.monster" not in text:
        continue
    new, n = OLD_URL.subn(NEW_URL, text)
    if n:
        f.write_text(new, encoding="utf-8")
        urls += n
        print("updater url patched in", f)
if urls == 0:
    sys.exit("updater urls not found - patch not applied")
for f in root.rglob("*"):
    if f.is_file() and f.suffix in (".smali", ".xml") and "vsindia" in f.read_text(encoding="utf-8", errors="ignore"):
        print("WARNING vendor host still referenced in", f)

REMOVE = re.compile(
    r"^(?P<ind>[ \t]*)(?P<call>invoke-(?P<kind>virtual|interface) \{(?P<a>[vp]\d+), (?P<b>[vp]\d+)\}, "
    r"Ljava/util/(?P<cls>ArrayList|List);->remove\(I\)Ljava/lang/Object;)"
    r"(?P<mr>\n[ \t]*move-result-object [vp]\d+)?",
    re.M,
)
METHOD = re.compile(r"\.method [^\n]*run\(\)V\n.*?\.end method", re.S)
LOCALS = re.compile(r"^([ \t]*)\.(locals|registers) (\d+)", re.M)

guards = 0
targets = list(root.rglob("MainActivity$18$2.smali"))
if not targets:
    sys.exit("MainActivity$18$2.smali not found")
for f in targets:
    text = f.read_text(encoding="utf-8")
    m = METHOD.search(text)
    if not m:
        sys.exit("run()V not found in " + str(f))
    body = m.group(0)
    r = REMOVE.search(body)
    if not r:
        sys.exit("remove(I) call not found in run()V of " + str(f))
    lm = LOCALS.search(body)
    if not lm:
        sys.exit("locals directive not found in " + str(f))
    old_n = int(lm.group(3))
    free = f"v{old_n}"
    ind, kind, a, b, cls = r.group("ind"), r.group("kind"), r.group("a"), r.group("b"), r.group("cls")
    guarded = (
        f"{ind}invoke-{kind} {{{a}}}, Ljava/util/{cls};->size()I\n"
        f"{ind}move-result {free}\n"
        f"{ind}if-ge {b}, {free}, :skip_ip_remove\n"
        f"{ind}{r.group('call')}{r.group('mr') or ''}\n"
        f"{ind}:skip_ip_remove"
    )
    new_body = body[: r.start()] + guarded + body[r.end():]
    new_body = LOCALS.sub(lambda x: f"{x.group(1)}.{x.group(2)} {old_n + 1}", new_body, count=1)
    f.write_text(text[: m.start()] + new_body + text[m.end():], encoding="utf-8")
    guards += 1
    print("ip-remove guard added in", f)

print(f"{urls} updater url(s), {guards} guard(s) patched")
