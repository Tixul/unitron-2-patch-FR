"""Catalogue COMPLET du texte de Biomotor Unitron 2 (J) -> out/catalogue.tsv

    python tools/extraire.py ROM [SORTIE.tsv]

Colonnes : adresse fichier (hex) · type · instr (adresse de la commande script, ou -) · japonais lisible.
Types :
  SCRIPT  texte de la commande 09 du script d'événements (boîte de dialogue)
  CHOIX   texte de la commande 13 (option d'un menu de choix)
  FICHE   nom dans une table de fiches à taille fixe (place = taille - 2), voir FICHES
  ACTEUR  texte des commandes 09/0A des scripts d'acteurs (2e interpréteur 0x228C0E, script2.py)
  POINTE  chaîne (…FF00) visée par un pointeur de 3 ou 4 octets
  SUITE   chaîne qui suit une chaîne retenue (FF00 juste avant) : lue en séquence / par index
Les chaînes doivent être plausibles (codes connus, au moins un kana ou une lettre).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script as S   # noqa: E402
import table as T    # noqa: E402

BASE = 0x200000
CTRL_OK = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07}
MAXLEN = 600


def chaine(rom, o, vide_ok=False):
    """Octets de o jusqu'au FF00 exclu, ou None si ce n'est pas du texte plausible.
    vide_ok : accepte une chaîne sans lettre (ponctuation seule, « …… ») — pour un texte CITÉ par
    une commande d'affichage."""
    i = o
    n_txt = 0
    while i - o < MAXLEN:
        c = rom[i]
        if c == 0xFF:
            c2 = rom[i + 1]
            if c2 == 0x00:
                if n_txt == 0 and not (vide_ok and i > o):
                    return None
                return rom[o:i]
            if c2 not in CTRL_OK:
                return None
            i += 2; continue
        if c == 0xFE:
            if rom[i + 1] > 0x24:
                return None
            i += 2; continue
        if c not in T.JP:
            return None
        if 0x01 <= c <= 0xBD:
            n_txt += 1
        i += 1
    return None


def plausible(b):
    s = T.lisible(b)
    k = T.kana(s)
    lat = sum(1 for ch in s if ch.isascii() and ch.isalpha())
    if k == 0 and lat < 2:
        return False
    # bruit graphique : longues répétitions du même octet
    if len(b) >= 6 and max(b.count(x) for x in set(b)) > 0.6 * len(b):
        return False
    return True


# Tables de fiches à taille fixe (code : base + (index-1)*taille), relevées le 21/11 :
# nom calé à gauche, FF00, puis zéros. Place = taille - 2 caractères (sauf relogement de la table).
FICHES = [(0x12F8B, 5), (0xE1B12, 8), (0xEBF3F, 10), (0xEC6E7, 10), (0xEF755, 8)]
# Tables de noms DÉPLACÉES sur la puce 2 par build.py, avec des fiches plus larges (21/11) :
# base -> (nouvelle taille, offset fichier de l'imm16 de « mul XHL,taille », de l'imm32 de « add XHL,base »)
# Chaque table n'est lue que par UNE routine (0x20B297/0x20B2C9/0x20B2F3/0x20B30F), vérifié.
NOUVELLE_TAILLE = 16          # 14 caractères + FF00
# 0xEBF3F (noms d'ENNEMIS) : 0x212646 recopie 10 octets du nom dans le tampon RAM 0x60A9 (aussi
# 0x212AA1, 0x213327, 0x215610 = nom de l'adversaire au câble). Seul, un nom long faisait REDÉMARRER
# la console (21/11). Corrigé par la routine NOM_ENNEMI (build.ROUTINES, asm/nom_ennemi.asm) :
# {FE20} lit le nom complet dans la table si le tampon en contient le début, sinon le tampon.
FICHES_RELOGEES = {0xE1B12: (0xB299, 0xB29D), 0xEF755: (0xB2CD, 0xB2D1),
                   0xEBF3F: (0xB2F7, 0xB2FB), 0xEC6E7: (0xB313, 0xB317),
                   0x12F8B: (0x12F82, 0x12F86)}   # éléments (0x212F7E : mul 5 / add), 3 car. -> 14


def place_fiche(base, sz):
    """Caractères permis pour un nom de la table `base` (taille d'origine sz)."""
    return (NOUVELLE_TAILLE if base in FICHES_RELOGEES else sz) - 2


def fiches(rom):
    out = {}
    for base, sz in FICHES:
        k = 0
        vides = 0
        while True:
            r = rom[base + k * sz: base + (k + 1) * sz]
            i = r.find(b'\xff\x00')
            if i == 0 and not any(r[2:]):          # fiche vide : on continue (64 de suite max)
                vides += 1
                if vides > 64:
                    break
                k += 1
                continue
            vides = 0
            if i <= 0 or any(r[i + 2:]):
                break
            b = chaine(rom, base + k * sz)
            if b is None or len(b) != i or not plausible(b):
                break
            out[base + k * sz] = (base, sz, k, b)
            k += 1
    return out


# écarts où chercher un AUTRE pointeur de texte pour reconnaître une table / une fiche
# (fiches mixtes texte + routine, ex. 0xE4A16 : 4 ptr de 3 octets + 1 octet, pas 13)
VOISINS = tuple(d for k in range(3, 17) for d in (-k, k))


# zones où un POINTEUR peut se trouver (code, tables, scripts) ; ailleurs = graphismes : de faux
# « pointeurs » y ont été réécrits par le premier build (motif jaune sur le logo, 21/11)
ZONES_SOURCES = [(0x0, 0x30000), (0x50000, 0x60000), (0xB0000, 0x100000), (0x1A0000, 0x1C0000)]
# fausses entrées repérées à l'écran (octets de table + vrai texte collés) : la vraie suit
EXCLURE = {0x20CC7, 0xE67, 0x11C720, 0x20DE9, 0x20D54}   # 0x20CC7 « ※しめ +しめ ジェス » (vrai nom en 0x20CCF) ; 0xE67, 0x11C720 = bruit cité par du code
# vrais débuts de texte collés derrière du code (vus à l'écran), cités par une table
FORCER = {0x213B9, 0x20DF5, 0x20D5C}   # 0x20DF5 titre de saisie derrière la table 0x20DE9 ; « ひらがな » (saisie du nom), après un ret ; table 0x2213D3
REFS = {}   # rempli par catalogue() : offset d'une chaîne POINTE -> [offsets des pointeurs (3 o)]


def analyses(rom):
    """Les deux interpréteurs, dans le bon ordre : script d'événements (entrées directes) →
    scripts d'acteurs → script d'événements complet (entrées supplémentaires hors acteurs)."""
    import script2 as S2
    base = S.Analyse(rom)
    base.parcourt(S.entrees_directes(rom))
    vu2, tx2, ent2, conf2 = S2.analyse(rom)
    interdit = bytearray(len(rom))
    for p, (op, n) in vu2.items():
        interdit[p:p + n] = b'\x01' * n
    for t, (op, p, b) in tx2.items():
        interdit[t:t + len(b) + 2] = b'\x01' * (len(b) + 2)
    an = S.analyse_complete(rom, interdit)
    return an, vu2, tx2


def catalogue(rom):
    an, vu2, tx2 = analyses(rom)
    lignes = {}
    occupe = bytearray(len(rom))
    for p, (op, n) in an.vu.items():
        occupe[p:p + n] = b'\x01' * n
    for t, (op, p, f) in an.textes.items():
        lignes[t] = ('SCRIPT' if op == 0x09 else 'CHOIX', p, rom[t:f - 2])
    for p, (op, n) in vu2.items():
        occupe[p:p + n] = b'\x01' * n
    for t, (op, p, b) in tx2.items():
        lignes.setdefault(t, ('ACTEUR', p, b))
    for o, (base, sz, k, b) in fiches(rom).items():
        lignes[o] = ('FICHE', None, b)
        occupe[o:o + sz] = b'\x01' * sz
    # cibles de pointeurs (3 octets ; un pointeur 4 octets a le même début) : source -> cible
    src = {}
    for i in range(len(rom) - 3):
        if 0x20 <= rom[i + 2] <= 0x3F and not occupe[i] and any(lo <= i < hi for lo, hi in ZONES_SOURCES):
            src[i] = (rom[i] | rom[i + 1] << 8 | rom[i + 2] << 16) - BASE

    def charge_par_code(j):
        # ld rr,imm32 (40-47 … 00) ou lda rr,(adr24) (F2 … 30-37) : adresse chargée par du code
        return ((0x40 <= rom[j - 1] <= 0x47 and rom[j + 3] == 0x00)
                or (rom[j - 1] == 0xF2 and 0x30 <= rom[j + 3] <= 0x37))

    def debut_ok(o):
        if o < 0x100 or o >= len(rom) - 2 or occupe[o] or o in lignes:
            return False
        if o in FORCER:
            return True
        if rom[o - 2] == 0xFF and rom[o - 1] == 0x00:
            return True
        # commence par « efface la boîte » / un nom inséré : début de texte certain, même collé
        # derrière une table de pointeurs (combat 0xF05DA…)
        # (« FF FF » devant n'est pas un code de contrôle : menu de combat 0xEFF6x derrière des FF)
        # « FE FF » non plus (paramètre d'insertion ≤ 0x24) : infos d'arme en combat 0xC15B
        if rom[o] == 0xFF and rom[o + 1] in (0x02, 0x05, 0x06, 0x07) and (rom[o - 1] not in (0xFF,) or rom[o - 2] == 0xFF):
            return True
        # juste après une table de pointeurs (3 octets : xx xx 2x | 4 octets : xx xx 2x 00)
        if 0x20 <= rom[o - 1] <= 0x3F and rom[o - 4] == rom[o - 1] and rom[o - 7] == rom[o - 1]:
            return True
        if (rom[o - 1] == 0 and 0x20 <= rom[o - 2] <= 0x3F and rom[o - 5] == 0
                and rom[o - 6] == rom[o - 2]):
            return True
        pr = rom[o - 1]
        return pr not in T.JP and pr not in (0xFF, 0xFE) and rom[o - 2] not in (0xFF, 0xFE)

    cand = {}
    for i, o in src.items():
        if o in cand:
            continue
        code = charge_par_code(i)          # ld rr, imm32
        if not debut_ok(o):
            # cité par du code : le texte peut suivre n'importe quoi (ex. prologue 0x21572 après un ret)
            if not (code and 0x100 <= o < len(rom) - 2 and not occupe[o] and o not in lignes
                    and rom[o - 1] not in (0xFF, 0xFE)):
                continue
        b = chaine(rom, o)
        cand[o] = b if (b is not None and plausible(b)) else None
    cand = {o: b for o, b in cand.items() if b is not None}


    def en_table(i, o):
        # voisin = AUTRE pointeur de table, pas un « ld rr,imm32 » : sinon des opérandes de code
        # proches d'un ld passent pour une table (0x14BA8 « ld C,1 / ld B,0x2F » -> Options noir ;
        # 0x258CE « ld A,(0x5FA9) » en combat). Corrigé 21/11.
        return any(src.get(i + d) in cand and src.get(i + d) != o and not charge_par_code(i + d)
                   for d in VOISINS)

    retenues = {}
    for i, o in src.items():
        if o not in cand or o in retenues:
            continue
        code = charge_par_code(i)          # ld rr, imm32
        table = en_table(i, o)
        if (code or table) and not bruit(o, cand[o], code) and o not in EXCLURE:
            retenues[o] = ('POINTE', None, cand[o])
    # toutes les sources « fortes » de chaque chaîne retenue (à réécrire si on la déplace)
    refs = {}
    for i, o in src.items():
        if o in retenues:
            code = charge_par_code(i)
            table = en_table(i, o)
            if code or table:
                refs.setdefault(o, []).append(i)
    REFS.clear()
    REFS.update(refs)
    # suites : chaînes chaînées après une chaîne retenue
    file = sorted(retenues)
    vues = set(file)
    while file:
        o = file.pop()
        b = retenues[o][2]
        q = o + len(b) + 2
        if q in vues or q in lignes or occupe[q]:
            continue
        b2 = chaine(rom, q)
        if b2 is not None and plausible(b2) and not bruit(q, b2):
            retenues[q] = ('SUITE', None, b2)
            vues.add(q); file.append(q)
    # une chaîne retenue qui chevauche une autre (début au milieu) : on garde la plus longue
    tout = dict(retenues)
    fins = sorted((o, o + len(v[2])) for o, v in tout.items())
    for k in range(1, len(fins)):
        a0, a1 = fins[k - 1]
        b0, b1 = fins[k]
        if b0 < a1 + 2 and b0 in tout and a0 in tout:
            del tout[b0]
    lignes.update(tout)
    blocs(rom, lignes, occupe)
    return lignes


# zones où une chaîne « orpheline » n'est que du bruit (graphismes, cartes)
ZONES_BRUIT = [(0x0, 0x10000), (0xB4000, 0xB7000), (0x100000, 0x1A0000), (0x1C0000, 0x200000)]
_OK_QUAL = set('ー…!?。、 ・「」【】<>,~★')


def qualite(b):
    import re
    s = re.sub(r'\{(n|p|J|P|FE..|FF..)\}', '', T.lisible(b))
    if not s:
        return 0.0
    bon = sum(1 for c in s if '぀' <= c <= 'ヿ' or c in _OK_QUAL or c.isdigit() or 'A' <= c <= 'Z')
    return bon / len(s)


_OK_LIB = _OK_QUAL | set(':/＊―%()+=◀▶')


def table_lue(b):
    """Table de pointeurs de 3/4 octets lue comme du texte : un octet sur 3 (ou 4) constant, dans
    0x20-0x3F (octet fort d'une adresse 0x2xxxxx), au moins 4 fois de suite."""
    b = bytes(b)
    for pas in (3, 4):
        for d in range(pas):
            run, prec = 0, None
            for j in range(d, len(b), pas):
                v = b[j]
                if 0x20 <= v <= 0x3F and v == prec:
                    run += 1
                    if run >= 3:
                        return True
                else:
                    run = 0
                prec = v
    return False


def bruit(o, b, code=False):
    """Fausse chaîne : zone graphique, octets de code ou table de pointeurs lus comme du texte
    (symboles jamais présents dans un vrai texte, ou trop peu de caractères de texte)."""
    import re
    # une chaîne citée par une instruction (ld reg, imm) peut vivre dans la zone du code (0xC15B)
    if not code and any(lo <= o < hi for lo, hi in ZONES_BRUIT):
        return True
    if table_lue(b):
        return True
    s = T.lisible(b)
    if any(c in s for c in '⌐◘＼^_◎×'):
        return True
    s2 = re.sub(r'\{(n|p|J|P|FE..|FF..)\}', '', s)
    if not s2:
        return False
    bon = sum(1 for c in s2 if '぀' <= c <= 'ヿ' or c in _OK_LIB or c.isdigit() or 'A' <= c <= 'Z')
    return bon / len(s2) < 0.8


def blocs(rom, lignes, occupe):
    """Texte resté sans mécanisme d'accès connu (lu par index « n-ième chaîne », doublons morts…) :
    type BLOC, traduit SUR PLACE avec un budget d'octets partagé par bloc de chaînes contiguës
    (l'ordre et le début du bloc ne bougent pas). instr = début du bloc."""
    cov = bytearray(occupe)
    for o, (t, p, b) in lignes.items():
        cov[o:o + len(b) + 2] = b'\x01' * (len(b) + 2)
    orph = []
    for o in range(0x100, len(rom) - 2):
        if rom[o - 2] == 0xFF and rom[o - 1] == 0 and not cov[o]:
            if any(lo <= o < hi for lo, hi in ZONES_BRUIT):
                continue
            b = chaine(rom, o)
            if (b and plausible(b) and T.kana(T.lisible(b)) >= 2 and qualite(b) >= 0.9 and not bruit(o, b)
                    and not any(cov[o:o + len(b)])):
                orph.append((o, b))
    debut = None
    fin_prec = None
    for o, b in orph:
        if o != fin_prec:
            debut = o
        lignes[o] = ('BLOC', debut, b)
        fin_prec = o + len(b) + 2


def main():
    rom = open(sys.argv[1], 'rb').read()
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'out', 'catalogue.tsv')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    lignes = catalogue(rom)
    with open(out + '.tmp', 'w', encoding='utf-8') as f:
        f.write('# adresse\ttype\tinstr\tjaponais\n')
        for o in sorted(lignes):
            typ, p, b = lignes[o]
            f.write('%06X\t%s\t%s\t%s\n' % (o, typ, '%06X' % p if p is not None else '-', T.lisible(b)))
    os.replace(out + '.tmp', out)
    import collections
    c = collections.Counter(v[0] for v in lignes.values())
    z = collections.Counter((o >> 16, v[0]) for o, v in lignes.items() if v[0] in ('POINTE', 'SUITE'))
    print(dict(c), 'total', len(lignes))
    print('car. JP différents', sum(len(set(T.lisible(v[2]) for v in lignes.values())), 0) if False else
          sum(len(x) for x in set(T.lisible(v[2]) for v in lignes.values())))
    for k in sorted(set(k for k, t in z)):
        print('  %06X  pointe %4d  suite %4d' % (k << 16, z[(k, 'POINTE')], z[(k, 'SUITE')]))


if __name__ == '__main__':
    main()
