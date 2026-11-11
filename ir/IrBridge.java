package com.android.vs.wireless.remote;

import android.content.Context;
import android.hardware.ConsumerIrManager;

/**
 * IR fallback for phones with a blaster. Used only while no TV is connected over Wi-Fi; the key
 * codes are the Android codes the Wi-Fi remote already sends, mapped to the TV's NEC 0x20/0xDF keys.
 */
public final class IrBridge {
    private static final int ADDRESS = 0x20;

    private IrBridge() {
    }

    private static int command(int keyCode) {
        switch (keyCode) {
            case 3:
                return 0x08; // home
            case 4:
                return 0x01; // back
            case 19:
                return 0x47; // up
            case 20:
                return 0x4D; // down
            case 21:
                return 0x49; // left
            case 22:
                return 0x4B; // right
            case 23:
                return 0x0E; // ok
            case 24:
                return 0x5C; // volume up
            case 25:
                return 0x0C; // volume down
            case 82:
                return 0x4A; // menu
            case 164:
                return 0x0B; // mute
            default:
                return -1;
        }
    }

    private static ConsumerIrManager emitter(Context ctx) {
        ConsumerIrManager cir = (ConsumerIrManager) ctx.getSystemService(Context.CONSUMER_IR_SERVICE);
        return (cir != null && cir.hasIrEmitter()) ? cir : null;
    }

    /** tvIp unchanged when a TV is known; a non-null marker when there is none but the phone can send IR. */
    public static String tvOrIr(Context ctx, String tvIp) {
        if (tvIp != null) {
            return tvIp;
        }
        return emitter(ctx) != null ? "ir" : null;
    }

    /** True when the message was sent as IR, so the Wi-Fi sender must be skipped. */
    public static boolean trySend(Context ctx, String tvIp, String msg) {
        if (tvIp != null || msg == null) {
            return false;
        }
        int cmd;
        try {
            cmd = command(Integer.parseInt(msg));
        } catch (NumberFormatException e) {
            return false;
        }
        if (cmd < 0) {
            return false;
        }
        try {
            ConsumerIrManager cir = emitter(ctx);
            if (cir == null) {
                return false;
            }
            cir.transmit(38000, pattern(ADDRESS, cmd));
            return true;
        } catch (RuntimeException e) {
            return false;
        }
    }

    /** NEC frame: 9 ms + 4.5 ms leader, address, ~address, command, ~command (LSB first), stop mark. */
    static int[] pattern(int address, int command) {
        int[] p = new int[67];
        int i = 0;
        p[i++] = 9000;
        p[i++] = 4500;
        int[] bytes = {address, address ^ 0xFF, command, command ^ 0xFF};
        for (int b : bytes) {
            for (int bit = 0; bit < 8; bit++) {
                p[i++] = 560;
                p[i++] = ((b >> bit) & 1) != 0 ? 1690 : 560;
            }
        }
        p[i] = 560;
        return p;
    }
}
