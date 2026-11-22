"""Analyseur du script d'événements de Biomotor Unitron 2 (interpréteur 0x213895, table 0x2138B8).

    python tools/script.py ROM [--dump FICHIER.txt]

Parcourt le script en suivant le flot depuis les points d'entrée, comme l'interpréteur
(36 commandes, FORMAT.md). Sort : couverture, textes (commandes 09 et 13), erreurs.
"""
import re
import struct
import sys

BASE = 0x200000
OP_MAX = 0x23

# opcode -> (forme, longueur des opérandes avant un éventuel texte)
# formes : n = normal, end = fin de branche, jmp = saut (adr3 à l'offset 0), call = appel,
# cj = saut conditionnel (adr3 à l'offset donné), txt = texte après les opérandes
SPEC = {
    0x00: ('n', 0), 0x01: ('end', 1), 0x02: ('jmp', 3), 0x03: ('call', 3), 0x04: ('n', 3),
    0x05: ('n', 1), 0x06: ('n', 1), 0x07: ('cj1', 4), 0x08: ('cj1', 4), 0x09: ('txt', 1),
    0x0A: ('n', 2), 0x0B: ('n', 2), 0x0C: ('n', 1), 0x0D: ('n', 1), 0x0E: ('n', 1),
    0x0F: ('n', 1), 0x10: ('n', 1), 0x11: ('n', 1), 0x12: ('n', 1), 0x13: ('choix', 3),
    0x14: ('menu', 3), 0x15: ('n', 2), 0x16: ('n', 2), 0x17: ('n', 2), 0x18: ('cj2', 5),
    0x19: ('cj2', 5), 0x1A: ('cj2', 5), 0x1B: ('n', 2), 0x1C: ('table', 0), 0x1D: ('n', 1),
    0x1E: ('n', 0), 0x1F: ('end', 1), 0x20: ('n', 2), 0x21: ('cj0_4', 4), 0x22: ('mem', 4),
    0x23: ('end', 0),
}


def a24(rom, p):
    return rom[p] | rom[p + 1] << 8 | rom[p + 2] << 16


def fin_texte(rom, p):
    """Comme sub 0x208B98 : avance jusqu'après la première paire FF 00."""
    while True:
        b = rom[p]; p += 1
        if b == 0xFF:
            b2 = rom[p]; p += 1
            if b2 == 0x00:
                return p


def entrees_directes(rom):
    """XHL immédiat chargé juste avant `call 0x2137F6`."""
    out = []
    for m in re.finditer(rb'\x1d\xf6\x37\x21', rom):
        i = m.start()
        if rom[i - 5] == 0x43:
            v = struct.unpack_from('<I', rom, i - 4)[0]
            out.append(v - BASE)
    return out


class Analyse:
    def __init__(self, rom, connu=None):
        self.rom = rom
        self.connu = connu or {}   # instructions déjà validées ailleurs : on s'y arrête
        self.vu = {}          # offset instr -> (op, longueur)
        self.textes = {}      # offset texte -> (op, offset instr, fin)
        self.erreurs = []
        self.pile = []

    def valide(self, off):
        return 0x100 <= off < len(self.rom)

    def ajoute(self, off, d):
        if not self.valide(off):
            self.erreurs.append(('saut hors ROM', d, off))
        else:
            self.pile.append(off)

    def parcourt(self, entrees):
        self.pile = list(entrees)
        rom = self.rom
        while self.pile:
            p = self.pile.pop()
            while True:
                if p in self.vu or p in self.connu:
                    break
                if not self.valide(p):
                    self.erreurs.append(('hors ROM', p, p)); break
                op = rom[p]
                if op > OP_MAX:
                    self.erreurs.append(('opcode %02X' % op, p, p)); break
                forme, n = SPEC[op]
                q = p + 1
                suite = True
                if forme == 'txt':
                    t = q + n
                    f = fin_texte(rom, t)
                    self.textes[t] = (op, p, f)
                    q = f
                elif forme == 'choix':
                    self.ajoute(a24(rom, q) - BASE, p)
                    t = q + 3
                    f = fin_texte(rom, t)
                    self.textes[t] = (op, p, f)
                    q = f
                elif forme in ('jmp', 'menu'):
                    self.ajoute(a24(rom, q) - BASE, p); q += n; suite = False
                elif forme == 'call':
                    self.ajoute(a24(rom, q) - BASE, p); q += n
                elif forme == 'cj1':
                    self.ajoute(a24(rom, q + 1) - BASE, p); q += n
                elif forme == 'cj2':
                    self.ajoute(a24(rom, q + 2) - BASE, p); q += n
                elif forme == 'cj0_4':
                    self.ajoute(a24(rom, q) - BASE, p); q += n
                elif forme == 'mem':
                    v = struct.unpack_from('<I', rom, q)[0] - BASE
                    if self.valide(v) and rom[v] <= OP_MAX:
                        self.ajoute(v, p)
                    q += n
                elif forme == 'table':
                    # entrées adr3 tant qu'elles visent le script ; borne prudente
                    k = 0
                    while k < 16:
                        v = a24(rom, q + 3 * k) - BASE
                        if not (0x1A0000 <= v < 0x1C0000):
                            break
                        self.ajoute(v, p); k += 1
                    self.vu[p] = (op, 1 + 3 * k)
                    break
                elif forme == 'end':
                    q += n; suite = False
                else:
                    q += n
                self.vu[p] = (op, q - p)
                if not suite:
                    break
                p = q


ZONES_SCRIPT = [(0x50000, 0x60000), (0x1A0000, 0x1C0000)]


def entrees_supplementaires(rom, base, interdit=None):
    """Entrées non appelées directement (scripts de l'arène, du câble…) : toute cible de pointeur
    de 3 octets dont le parcours (arrêté sur le déjà-connu) est SANS erreur, contient au moins un
    texte, et dont tous les textes sont du texte plausible. Renvoie la liste des entrées gardées."""
    import extraire as X
    connu = dict(base.vu)
    garde = []
    vues = set()
    for i in range(len(rom) - 3):
        if not (0x20 <= rom[i + 2] <= 0x3F):
            continue
        t = a24(rom, i) - BASE
        if t in vues or t in connu or not (0x100 <= t < len(rom)) or rom[t] > OP_MAX:
            continue
        vues.add(t)
        a = Analyse(rom, connu)
        a.parcourt([t])
        if a.erreurs or not a.textes or len(a.vu) < 2:
            continue
        if any(X.chaine(rom, tx, vide_ok=True) is None for tx in a.textes):
            continue
        if interdit is not None and (any(interdit[q] for q in a.vu)
                                     or any(interdit[tx] for tx in a.textes)):
            continue
        # le script d'événements ne vit que dans ces deux zones (faux positif « くしハンガー »
        # en 0x1AEB1 = libellé de menu précédé d'octets de position)
        if not all(any(lo <= q < hi for lo, hi in ZONES_SCRIPT) for q in a.vu):
            continue
        garde.append(t)
        connu.update(a.vu)
    return garde


def analyse_complete(rom, interdit=None):
    """Script d'événements entier : entrées directes + entrées supplémentaires validées
    (interdit : octets déjà attribués, p. ex. aux scripts d'acteurs)."""
    a = Analyse(rom)
    ent = entrees_directes(rom)
    a.parcourt(ent)
    ent = ent + entrees_supplementaires(rom, a, interdit)
    b = Analyse(rom)
    b.parcourt(ent)
    b.entrees = ent
    return b


def main():
    rom = open(sys.argv[1], 'rb').read()
    a = Analyse(rom)
    ent = entrees_directes(rom)
    a.parcourt(ent)
    octets = sum(n for op, n in a.vu.values()) + sum(f - t for t, (op, p, f) in a.textes.items())
    print('entrées', len(ent), 'instructions', len(a.vu), 'textes', len(a.textes),
          'octets', octets, 'erreurs', len(a.erreurs))
    for e in a.erreurs[:20]:
        print('  ', e[0], hex(e[1]), hex(e[2]))


if __name__ == '__main__':
    main()
