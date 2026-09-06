import struct

HOOK = 0x8508
STUB = 0x2BB94
RESTORE = STUB + 96
REJOIN = RESTORE + 4
EPILOGUE_CONT = 0x850C
FD6A = 0xFD6A
MAGIC = 0x5A590000
COUNTS = 0x20001854

DISPLACED = bytes.fromhex("b2502254")

ZERO, RA, T0, T1, T2, S0, S1, T3, T4, T5 = 0, 1, 5, 6, 7, 8, 9, 28, 29, 30


def i_type(op, f3, rd, rs1, imm):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def s_type(op, f3, rs1, rs2, imm):
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 0x1F) << 7) | op


def u_type(op, rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | op


def b_type(op, f3, rs1, rs2, off):
    return (((off >> 12) & 1) << 31) | (((off >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) \
        | (f3 << 12) | (((off >> 1) & 0xF) << 8) | (((off >> 11) & 1) << 7) | op


def j_type(op, rd, off):
    return (((off >> 20) & 1) << 31) | (((off >> 1) & 0x3FF) << 21) | (((off >> 11) & 1) << 20) \
        | (((off >> 12) & 0xFF) << 12) | (rd << 7) | op


LW, LBU, ADDI, SW, LUI, BRANCH, JAL = 0x03, 0x03, 0x13, 0x23, 0x37, 0x63, 0x6F


def build_stub():
    out = []

    def at(i):
        return STUB + 4 * i

    words = [
        i_type(LW, 2, T0, S1, 4),
        u_type(LUI, T1, 0x5A590),
        b_type(BRANCH, 1, T0, T1, RESTORE - at(2)),
        u_type(LUI, T0, 0x20002),
        i_type(ADDI, 0, T0, T0, -0x7AC),
        i_type(LW, 2, T1, T0, 0),
        i_type(LW, 2, T2, T0, 4),
        i_type(LW, 2, T3, T0, 8),
        i_type(LW, 2, T4, T0, 12),
        s_type(SW, 2, S0, T1, 8),
        s_type(SW, 2, S0, T2, 12),
        s_type(SW, 2, S0, T3, 16),
        s_type(SW, 2, S0, T4, 20),
        i_type(LBU, 4, T5, S1, 3),
        b_type(BRANCH, 0, T5, ZERO, RESTORE - at(14)),
        i_type(LW, 2, T1, S1, 8),
        i_type(LW, 2, T2, S1, 12),
        i_type(LW, 2, T3, S1, 16),
        i_type(LW, 2, T4, S1, 20),
        s_type(SW, 2, T0, T1, 0),
        s_type(SW, 2, T0, T2, 4),
        s_type(SW, 2, T0, T3, 8),
        s_type(SW, 2, T0, T4, 12),
        j_type(JAL, RA, FD6A - at(23)),
    ]
    for w in words:
        out.append(struct.pack("<I", w))
    return b"".join(out)


def patches():
    stub = build_stub()
    assert len(stub) == 96, len(stub)
    hook = struct.pack("<I", j_type(JAL, ZERO, STUB - HOOK))
    rejoin = struct.pack("<I", j_type(JAL, ZERO, EPILOGUE_CONT - REJOIN))
    return [(HOOK, hook), (STUB, stub), (RESTORE, DISPLACED), (REJOIN, rejoin)]


def verify():
    from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC
    md = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    for addr, data in patches():
        print(f"\n== @0x{addr:X} ({len(data)}B) {data.hex()} ==")
        for ins in md.disasm(data, addr):
            print(f"  0x{ins.address:X}: {ins.mnemonic:7}{ins.op_str}")


if __name__ == "__main__":
    verify()
    print("\n== apply-ready ==")
    for addr, data in patches():
        print(f"0x{addr:X} {' '.join('%02x' % b for b in data)}")
