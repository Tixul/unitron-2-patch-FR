"""Second interpréteur : scripts d'ACTEURS / de carte (boucle 0x228C0E, table 0x228C2E, 49 commandes).

    python tools/script2.py ROM

Opcode 1 octet, MASQUÉ & 0x3F (le décalage se fait sur 8 bits : 0x80 = 0x00) ; adresses 32 bits (pointeurs CPU 0x2xxxxx). Textes : 09/0A (fenêtre + ptr32 → FF00).
Les points d'entrée sont posés dans des structures d'acteurs (XHL+0) : on essaie chaque cible de pointeur
32 bits comme entrée ; un parcours n'est GARDÉ que s'il va au bout sans erreur et que tous ses textes
sont plausibles (début après FF00 ou après un octet non textuel). FORMAT.md.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extraire as X   # noqa: E402

BASE = 0x200000
OP_MAX = 0x30
# opcode -> (forme, longueur des opérandes)
#  n normal · txt (1 + ptr32 texte) · jmp ptr32 · end · tab4 (ptr32 vers table de 4 ptr32)
#  br2 (ptr32 a, ptr32 b, puis suite) · call ptr32 · ret · loop (1 + ptr32, + suite) · sel (1 + 2 ptr32)
SPEC = {
    0x00: ('n', 1), 0x01: ('n', 3), 0x02: ('n', 7), 0x03: ('n', 5), 0x04: ('n', 3), 0x05: ('n', 1),
    0x06: ('n', 2), 0x07: ('n', 1), 0x08: ('n', 3), 0x09: ('txt', 5), 0x0A: ('txt', 5), 0x0B: ('n', 6),
    0x0C: ('n', 6), 0x0D: ('n', 11), 0x0E: ('n', 9), 0x0F: ('n', 2), 0x10: ('n', 1), 0x11: ('n', 4),
    0x12: ('n', 2), 0x13: ('n', 2), 0x14: ('n', 0), 0x15: ('n', 1), 0x16: ('n', 1), 0x17: ('n', 1),
    0x18: ('n', 1), 0x19: ('n', 1), 0x1A: ('n', 0), 0x1B: ('n', 0), 0x1C: ('jmp', 4), 0x1D: ('tab4', 4),
    0x1E: ('br2', 8), 0x1F: ('call', 4), 0x20: ('ret', 0), 0x21: ('loop', 5), 0x22: ('n', 4),
    0x23: ('n', 1), 0x24: ('n', 2), 0x25: ('n', 1), 0x26: ('n', 1), 0x27: ('sel', 9), 0x28: ('n', 6),
    0x29: ('n', 0), 0x2A: ('n', 2), 0x2B: ('n', 0), 0x2C: ('n', 2), 0x2D: ('n', 0), 0x2E: ('n', 1),
    0x2F: ('end', 4), 0x30: ('end', 4),
}
TEXTES_FIXES = (0xB85E9, 0xB85ED, 0xB85F1)   # commandes 06 et 1B


def p32(rom, p):
    v = struct.unpack_from('<I', rom, p)[0]
    return v - BASE if BASE <= v < BASE + len(rom) else None


def texte_ok(rom, o):
    """Texte cité par 09/0A : n'importe quel octet peut le précéder (il suit souvent du bytecode),
    sauf le milieu d'un code FF xx / FE xx."""
    if o is None or o < 2:
        return None
    if rom[o - 1] in (0xFF, 0xFE) and not (rom[o - 2] == 0xFF and rom[o - 1] == 0x00):
        return None
    b = X.chaine(rom, o, vide_ok=True)
    return b


RAISON = []   # adresse de l'instruction fautive du dernier parcours rejeté


def parcours(rom, entree, interdit):
    """Parcours d'une entrée. Renvoie (instr {off:(op,n)}, textes {off:(op,instr,octets)}) ou None."""
    vu, textes, pile = {}, {}, [entree]
    while pile:
        p = pile.pop()
        while True:
            if p in vu:
                break
            if not (0x100 <= p < len(rom) - 16) or interdit[p]:
                RAISON[:] = [p]; return None
            op = rom[p] & 0x3F          # « sll 2, A » sur 8 bits : 0x80 s'exécute comme 0x00
            if op > OP_MAX:
                RAISON[:] = [p]; return None
            forme, n = SPEC[op]
            q = p + 1
            fin = False
            if forme == 'txt':
                t = p32(rom, q + 1)
                b = texte_ok(rom, t)
                if b is None:
                    RAISON[:] = [p]; return None
                textes[t] = (op, p, b)
            elif forme in ('jmp', 'call'):
                t = p32(rom, q)
                if t is None:
                    RAISON[:] = [p]; return None
                pile.append(t)
                fin = forme == 'jmp'
            elif forme == 'tab4':
                # table de ptr32 (souvent EN LIGNE juste après) ; index = 2*(0x4FE6)+(0x4FE7).
                # Retombe sur l'instruction suivante seulement si l'entrée choisie est nulle.
                tb = p32(rom, q)
                if tb is None:
                    RAISON[:] = [p]; return None
                nul = False
                for k in range(16):
                    v = struct.unpack_from('<I', rom, tb + 4 * k)[0]
                    if v == 0:
                        nul = True; continue
                    t = v - BASE
                    if not (0x100 <= t < len(rom)) or (rom[t] & 0x3F) > OP_MAX:
                        break
                    pile.append(t)
                fin = not nul
            elif forme in ('br2', 'sel'):
                # deux ptr32 (br2 : à q, q+4 ; sel : à q+1, q+5) ; suite seulement si l'un est nul
                d = 0 if forme == 'br2' else 1
                nul = False
                for k in (d, d + 4):
                    v = struct.unpack_from('<I', rom, q + k)[0]
                    if v == 0:
                        nul = True
                    elif p32(rom, q + k) is None:
                        RAISON[:] = [p]; return None
                    else:
                        pile.append(v - BASE)
                fin = not nul
            elif forme == 'loop':
                t = p32(rom, q + 1)
                if t is None:
                    RAISON[:] = [p]; return None
                pile.append(t)
            elif forme in ('ret', 'end'):
                fin = True
            vu[p] = (op, 1 + n)
            if len(vu) > 20000:
                RAISON[:] = [p]; return None
            if fin:
                break
            p = q + n
    return vu, textes


def analyse(rom):
    import script as S
    an = S.Analyse(rom)
    an.parcourt(S.entrees_directes(rom))
    interdit = bytearray(len(rom))
    for p, (op, n) in an.vu.items():
        interdit[p:p + n] = b'\x01' * n
    for t, (op, p, f) in an.textes.items():
        interdit[t:f] = b'\x01' * (f - t)
    cibles = set()
    for i in range(len(rom) - 4):
        if rom[i + 3] == 0 and 0x20 <= rom[i + 2] <= 0x3F:
            o = (rom[i] | rom[i + 1] << 8 | rom[i + 2] << 16) - BASE
            if 0x100 <= o < len(rom) and (rom[o] & 0x3F) <= OP_MAX and not interdit[o]:
                cibles.add(o)
    vu, textes, entrees = {}, {}, []
    for o in sorted(cibles):
        if o in vu:
            continue
        r = parcours(rom, o, interdit)
        if r is None:
            continue
        v, t = r
        if not t:          # un parcours sans texte ne prouve rien : ignoré
            continue
        entrees.append(o)
        vu.update(v)
        textes.update(t)
    # chevauchements instructions / textes = signe d'un faux parcours
    occ = {}
    conflits = 0
    for p, (op, n) in vu.items():
        for k in range(p, p + n):
            if k in occ and occ[k] != p:
                conflits += 1
            occ[k] = p
    return vu, textes, entrees, conflits


def main():
    rom = open(sys.argv[1], 'rb').read()
    vu, textes, entrees, conflits = analyse(rom)
    import collections
    print('entrées gardées', len(entrees), 'instructions', len(vu), 'textes', len(textes),
          'octets chevauchés', conflits)
    z = collections.Counter(t >> 16 for t in textes)
    print(sorted((hex(k << 16), n) for k, n in z.items()))
    z = collections.Counter(p >> 16 for p in vu)
    print('instr', sorted((hex(k << 16), n) for k, n in z.items()))


if __name__ == '__main__':
    main()
