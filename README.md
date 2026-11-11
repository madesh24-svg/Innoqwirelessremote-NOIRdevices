# Innoq wireless remote - phones without IR

Vendor Wi-Fi remote for the Innoq TV (`com.android.vs.wireless.remote` 2.1.2).

| File | Use on |
|---|---|
| `WirelessRemote.apk` | Original, unmodified. Phones with an IR blaster. |
| `WirelessRemote-noir.apk` | Patched. Phones without IR (stock app crashes on launch there). |

## Why the stock app crashes without IR

`MainActivity.initInfrared` calls `ConsumerIrManager.hasIrEmitter()` on the result of
`getSystemService("consumer_ir")`, which is null on phones with no IR blaster
(`NullPointerException`, app closes right after opening).

`patch_ir.py` adds a null check around each such call, so a missing IR service reads as
"no IR emitter". Nothing else is changed. The GitHub Actions workflow decompiles the original
with apktool, applies the patch, rebuilds, zipaligns and signs it with a one-off key.

## Installing

- The patched build is signed with a different key than the original, so uninstall the
  original first (its saved TV pairing is lost).
- Some phones (HyperOS) block `adb install`; copy the APK to the phone and install it from the
  file manager.

## IR keys without Wi-Fi

On a phone with an IR blaster, while no TV is connected over Wi-Fi, the arrow keys, OK, Back,
Home, Menu, Volume +/- and Mute are sent as IR (NEC address 0x20/0xDF) instead of showing
"connect the TV first". When a TV is connected over Wi-Fi nothing changes. Power keeps the
vendor's own IR code. Source, voice, keyboard, mouse and the app list stay Wi-Fi only.
`ir/IrBridge.java` is compiled in CI and added as a second dex; `patch_ir_keys.py` hooks it in.

## Updating

The patched app updates itself from this repo's latest release (menu, Update). The vendor's
update address (plain HTTP, no longer supported) is replaced by
`releases/latest/download/WirelessRemote.xml` over HTTPS. Each push to `main` builds, signs
(stable key, so updates install in place) and publishes `WirelessRemote-noir.apk` and the XML.

## Fixed

`MainActivity$18$2.run` removed an item from an already-empty device list
(`IndexOutOfBoundsException`); the remove is now skipped when the index is out of range.
