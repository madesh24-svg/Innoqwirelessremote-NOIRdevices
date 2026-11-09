"""Make a decompiled WirelessRemote tolerate phones with no IR blaster.

The stock app calls ConsumerIrManager.hasIrEmitter() on the result of
getSystemService("consumer_ir"), which is null on phones without IR, so
MainActivity crashes on start. Every such call gets a null check: a null
manager reads as "no IR emitter" (false).
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])

CALL = r"(?P<reg>[vp]\d+)\}, Landroid/hardware/ConsumerIrManager;->hasIrEmitter\(\)Z"
PATTERN = re.compile(
    r"(?P<ind>[ \t]*)invoke-virtual \{" + CALL + r"\n(?:[ \t]*\n)*[ \t]*move-result (?P<dst>[vp]\d+)"
)

count = 0


def repl(m):
    global count
    count += 1
    n = count
    ind, reg, dst = m.group("ind"), m.group("reg"), m.group("dst")
    return (
        f"{ind}if-eqz {reg}, :ir_null_{n}\n"
        f"{ind}invoke-virtual {{{reg}}}, Landroid/hardware/ConsumerIrManager;->hasIrEmitter()Z\n"
        f"{ind}move-result {dst}\n"
        f"{ind}goto :ir_end_{n}\n"
        f"{ind}:ir_null_{n}\n"
        f"{ind}const/16 {dst}, 0x0\n"
        f"{ind}:ir_end_{n}"
    )


for f in root.rglob("*.smali"):
    text = f.read_text(encoding="utf-8")
    if "hasIrEmitter" not in text:
        continue
    new = PATTERN.sub(repl, text)
    if new != text:
        f.write_text(new, encoding="utf-8")
        print("patched", f)

print(f"{count} call(s) patched")
if count == 0:
    sys.exit("no hasIrEmitter() call matched - patch not applied")
