"""Stage 2: send every mapped key over IR when the phone has an emitter and no TV is connected.

Hook B - MainActivity.sendBroadcastMSG(String): ask IrBridge.trySend first; skip the Wi-Fi send
         when it sent IR.
Hook A - MainActivity$13.onClick: the first read of TvIp (the "connect the TV first" gate) goes
         through IrBridge.tvOrIr, so on an IR phone the gate (toast + device search) is skipped.
"""
import re
import sys
from pathlib import Path
from typing import NoReturn

root = Path(sys.argv[1])


def die(msg: str, detail: str = "") -> NoReturn:
    text = msg + ((" | " + detail) if detail else "")
    text = text.replace("%", "%25").replace(chr(13), "").replace(chr(10), "%0A")
    print("::error::" + text)
    sys.exit(1)


PKG = "Lcom/android/vs/wireless/remote/"
MAIN = PKG + "MainActivity;"
BRIDGE = PKG + "IrBridge;"
LISTENER = PKG + "MainActivity$13;"

mains = list(root.rglob("MainActivity.smali"))
if len(mains) != 1:
    die(f"expected one MainActivity.smali, found {len(mains)}")
main_path = mains[0]
main = main_path.read_text(encoding="utf-8")

LOCALS = re.compile(r"^([ \t]*)\.(locals|registers) (\d+)[ \t]*$", re.M)


def method_span(text, header_re):
    m = re.search(header_re + r".*?\.end method", text, re.S)
    if not m:
        die("method not found: " + header_re)
    return m


# ---- Hook B -------------------------------------------------------------------------------
mb = method_span(main, r"\.method [^\n]*sendBroadcastMSG\(Ljava/lang/String;\)V\n")
body = mb.group(0)
lm = LOCALS.search(body)
if not lm:
    die("no .locals in sendBroadcastMSG")
n_locals = max(int(lm.group(3)), 1)
ind = lm.group(1)
hook_b = (
    f"{ind}iget-object v0, p0, {MAIN}->TvIp:Ljava/lang/String;\n"
    f"{ind}invoke-static {{p0, v0, p1}}, {BRIDGE}->trySend(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Z\n"
    f"{ind}move-result v0\n"
    f"{ind}if-eqz v0, :ir_not_sent\n"
    f"{ind}return-void\n"
    f"{ind}:ir_not_sent\n"
)
head = body[: lm.start()] + f"{ind}.{lm.group(2)} {n_locals}"
lines = body[lm.end():].split("\n")
DIRECTIVES = (".param", ".end param", ".prologue", ".line", ".local", ".end local", ".restart local")
at = None
in_annotation = False
for i, ln in enumerate(lines):
    s = ln.strip()
    if in_annotation:
        in_annotation = not s.startswith(".end annotation")
        continue
    if s.startswith(".annotation"):
        in_annotation = True
        continue
    if s == "" or s.startswith(DIRECTIVES):
        continue
    at = i
    break
if at is None:
    die("no instruction found in sendBroadcastMSG", body[:600])
new_body = head + "\n".join(lines[:at]) + "\n" + hook_b + "\n".join(lines[at:])
main = main[: mb.start()] + new_body + main[mb.end():]
main_path.write_text(main, encoding="utf-8")
print("hook B added in", main_path)

# ---- Hook A -------------------------------------------------------------------------------
targets = list(root.rglob("MainActivity$13.smali"))
if len(targets) != 1:
    die(f"expected one MainActivity$13.smali, found {len(targets)}")
lp = targets[0]
lt = lp.read_text(encoding="utf-8")
if not re.search(r"\.field [^\n]*this\$0:" + re.escape(MAIN), lt):
    die("this$0 field not found in MainActivity$13")
mo = method_span(lt, r"\.method [^\n]*onClick\(Landroid/view/View;\)V\n")
obody = mo.group(0)

# The gate is the first String getter whose result is tested with if-nez/if-eqz after only
# constants, e.g.  invoke-static {v0}, ...->access$2300(...)String / move-result-object v0 /
# const... / if-nez v0, :cond_0
NL = r"\n(?:[ \t]*\n)*"  # apktool puts a blank line after every instruction
CONSTS = r"(?:[ \t]*(?:const[^\n]*|\.line[^\n]*|\.local[^\n]*)" + NL + r")*"
READS = [
    re.compile(
        r"(?P<head>invoke-static \{[vp]\d+\}, " + re.escape(MAIN) + r"->access\$\d+\(" + re.escape(MAIN)
        + r"\)Ljava/lang/String;" + NL + r"[ \t]*move-result-object (?P<dst>[vp]\d+))" + NL + CONSTS
        + r"[ \t]*if-(?:nez|eqz) (?P=dst),"
    ),
    re.compile(
        r"(?P<head>iget-object (?P<dst>[vp]\d+), [vp]\d+, " + re.escape(MAIN) + r"->TvIp:Ljava/lang/String;)" + NL
        + CONSTS + r"[ \t]*if-(?:nez|eqz) (?P=dst),"
    ),
]
first = None
for rx in READS:
    m = rx.search(obody)
    if m and (first is None or m.start() < first.start()):
        first = m
if not first:
    die("TvIp gate not found in MainActivity$13.onClick", obody[:1800])
print("gate found:", first.group("head").replace("\n", " "))
ll = LOCALS.search(obody)
if not ll:
    die("no .locals in onClick")
old_n = int(ll.group(3))
free = f"v{old_n}"
dst = first.group("dst")
ind = ll.group(1)
insert = (
    f"\n{ind}iget-object {free}, p0, {LISTENER}->this$0:{MAIN}"
    f"\n{ind}invoke-static {{{free}, {dst}}}, {BRIDGE}->tvOrIr(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;"
    f"\n{ind}move-result-object {dst}"
)
obody = obody[: first.end("head")] + insert + obody[first.end("head"):]
obody = LOCALS.sub(lambda x: f"{x.group(1)}.{x.group(2)} {old_n + 1}", obody, count=1)
lt = lt[: mo.start()] + obody + lt[mo.end():]
lp.write_text(lt, encoding="utf-8")
print("hook A added in", lp)
