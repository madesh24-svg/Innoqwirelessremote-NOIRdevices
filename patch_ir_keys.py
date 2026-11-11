"""Stage 2: send every mapped key over IR when the phone has an emitter and no TV is connected.

Hook B - MainActivity.sendBroadcastMSG(String): ask IrBridge.trySend first; skip the Wi-Fi send
         when it sent IR.
Hook A - MainActivity$13.onClick: the first read of TvIp (the "connect the TV first" gate) goes
         through IrBridge.tvOrIr, so on an IR phone the gate (toast + device search) is skipped.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])


def die(msg, detail=""):
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
hook_b = (
    f"{lm.group(1)}.{lm.group(2)} {n_locals}\n"
    f"{lm.group(1)}iget-object v0, p0, {MAIN}->TvIp:Ljava/lang/String;\n"
    f"{lm.group(1)}invoke-static {{p0, v0, p1}}, {BRIDGE}->trySend(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Z\n"
    f"{lm.group(1)}move-result v0\n"
    f"{lm.group(1)}if-eqz v0, :ir_not_sent\n"
    f"{lm.group(1)}return-void\n"
    f"{lm.group(1)}:ir_not_sent"
)
new_body = body[: lm.start()] + hook_b + body[lm.end():]
main = main[: mb.start()] + new_body + main[mb.end():]
main_path.write_text(main, encoding="utf-8")
print("hook B added in", main_path)

# ---- Hook A -------------------------------------------------------------------------------
# synthetic getters for MainActivity.TvIp, e.g. access$300(MainActivity)String
accessors = set()
for m in re.finditer(
    r"\.method static synthetic (access\$\d+)\(" + re.escape(MAIN) + r"\)Ljava/lang/String;\n.*?\.end method",
    main,
    re.S,
):
    if re.search(r"iget-object [vp]\d+, [vp]\d+, " + re.escape(MAIN) + r"->TvIp:Ljava/lang/String;", m.group(0)):
        accessors.add(m.group(1))
print("TvIp accessors:", sorted(accessors) or "none (direct field reads)")

targets = list(root.rglob("MainActivity$13.smali"))
if len(targets) != 1:
    die(f"expected one MainActivity$13.smali, found {len(targets)}")
lp = targets[0]
lt = lp.read_text(encoding="utf-8")
if not re.search(r"\.field [^\n]*this\$0:" + re.escape(MAIN), lt):
    die("this$0 field not found in MainActivity$13")
mo = method_span(lt, r"\.method [^\n]*onClick\(Landroid/view/View;\)V\n")
obody = mo.group(0)

READS = []
if accessors:
    alt = "|".join(re.escape(a) for a in sorted(accessors))
    READS.append(re.compile(
        r"invoke-static \{[vp]\d+\}, " + re.escape(MAIN) + r"->(?:" + alt + r")\(" + re.escape(MAIN)
        + r"\)Ljava/lang/String;\n[ \t]*move-result-object (?P<dst>[vp]\d+)"
    ))
READS.append(re.compile(
    r"iget-object (?P<dst>[vp]\d+), [vp]\d+, " + re.escape(MAIN) + r"->TvIp:Ljava/lang/String;"
))
first = None
for rx in READS:
    m = rx.search(obody)
    if m and (first is None or m.start() < first.start()):
        first = m
if not first:
    die("TvIp read not found in MainActivity$13.onClick", obody[:1800])
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
obody = obody[: first.end()] + insert + obody[first.end():]
obody = LOCALS.sub(lambda x: f"{x.group(1)}.{x.group(2)} {old_n + 1}", obody, count=1)
lt = lt[: mo.start()] + obody + lt[mo.end():]
lp.write_text(lt, encoding="utf-8")
print("hook A added in", lp)
