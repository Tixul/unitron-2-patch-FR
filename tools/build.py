"""Fabrique la ROM traduite de Kikou Seiki Unitron (Biomotor Unitron 2, Japon) et le patch IPS.

    python tools/build.py --rom ROM_JP.ngc [--lang fr] [--verif] [--ips]
        -> out/<code>.ngc et, avec --ips, out/<code>.ips (patch pour la ROM JAPONAISE)
    python tools/build.py ROM_JP.ngc SORTIE.ngc --tout-en-saut
        test : sans traduction, fait passer TOUT le texte par les mécanismes de relogement avec le
        japonais d'origine -> le jeu doit être identique à l'original

- La ROM d'entrée est vérifiée (CRC32 84580D66, 2 097 152 octets). Sortie : 4 Mio. Puce 1 = ROM d'origine
  modifiée ; puce 2 (fichier 0x200000 = CPU 0x800000) = tout le neuf.
- Traduction : tous les lang/<code>/*.txt. Lignes `@ADRESSE<TAB>texte` (entrée du catalogue à cette
  adresse fichier hex, voir tools/extraire.py) ; `#` = commentaire. Texte : table.FR ; {n} ligne,
  {p} efface la boîte, {J}/{P}/{FF07} noms du pilote / du partenaire / de l'Elel, {FExx} insertion de
  combat, {box} = boîte suivante (scènes et personnages seulement).
- Placement par type (catalogue, extraire.py) :
  SCRIPT/CHOIX  la commande devient `02 adr3` (saut) vers un bloc neuf `09 f … FF00 [09 0 …]` + `02 retour`.
  ACTEUR        texte sur la puce 2, pointeur 32 bits réécrit ; avec {box} : `1C adr` vers
                `09 f p1 … 0X f pN 1C retour`.
  POINTE(+SUITE) chaîne et sa suite déplacées ensemble ; tous les pointeurs forts réécrits.
  FICHE         tables de noms déplacées en fiches de 16 octets (14 caractères).
  BLOC          sur place, budget d'octets partagé par le bloc (ordre conservé).
- Aussi : police (police.py), grille de saisie du nom (grille.py), écran-titre (titre.py,
  gfx/titre_fr.png), fenêtres élargies (PATCHS_FENETRES), routine NOM_ENNEMI (asm/nom_ennemi.asm).
- --verif : contrôle les traductions (encodage, place des noms et des blocs) sans écrire la ROM.
Détails : FORMAT.md.
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extraire as X   # noqa: E402
import table as T      # noqa: E402

BASE = 0x200000
PUCE2 = 0x200000          # offset fichier de la puce 2
PUCE2_CPU = 0x800000
ICI = os.path.dirname(os.path.abspath(__file__))
AVERT = []


# Routines ajoutées : (adresse CPU, code, [(offset fichier, octets d'origine, octets neufs)])
ROUTINES = [
    # NOM_ENNEMI (asm/nom_ennemi.asm) : {FE20} affiche le nom COMPLET de l'ennemi (table élargie)
    # au lieu du tampon RAM de 10 octets 0x60A9 (gardé pour le nom de l'adversaire au câble).
    (0x800100, bytes.fromhex('3a39eba8c1a660271df3b220eb8942a96000002008c5e421c5e8f16e05c81cf568'
                             '0543a9600000595a1b683321'),
     [(0x13325, bytes.fromhex('3b43a96000001e3a005b0e'), bytes.fromhex('3b1d0001805b0e00000000'))]),
]


# Fenêtres élargies (phase menus) : (offset fichier, octets d'origine, octets neufs, raison).
# Fenêtre = 0x209FA4 (A=n°, C=largeur, B=hauteur, HL=1re tuile) ; position = 0x20A055 (C=colonne,
# B=rangée ; B>=32 -> plan SCR2) ; le plan SCR2 défile de (0x49E4, 0x49E6) = (X, Y).
# Limite : les tuiles du cadre sont fixes en 0x1F5-0x1FE -> fenêtre 3 (base 0x1B8) = 61 tuiles.
PATCHS_FENETRES = [
    (0xBE9F, b'\x08', b'\x0c', "combat : choix d'arme, largeur 8 -> 12 (10 car. ; 12x5 = 60 tuiles, 61 au plus avant le cadre 0x1F5)"),
    (0xBEC2, b'\xb0', b'\xd0', "combat : choix d'arme, défilement X du SCR2 +32 (fenêtre décalée de 4 col. à gauche, bord droit inchangé)"),
    (0x14D57, b'\x20', b'\x38', "options, effacer : curseur x = n*0x20+0x50 -> n*0x38+0x38 (col. 5 et 12 : « Toutes » / « Une »)"),
    (0x14D5B, b'\x50', b'\x38', "options, effacer : abscisse de départ du curseur (voir ci-dessus)"),
    (0xBFCC, b'\x60', b'\x40',"combat : choix d'arme, abscisse du curseur 96 -> 64 (ld BC,0x0060 en 0x20BFCB, suit la fenêtre)"),
]


# Chaînes POINTE aussi lues par un pointeur EN LEUR MILIEU : traduites sur place, même longueur exacte
SUR_PLACE = {
    0x14630: "titre de l'écran des fichiers ; 0x2144CF lit l'octet 14 (« {n}     <みしよう> » des cases vides)",
}


def cpu(off):
    """Offset fichier (ROM 4 Mio) -> adresse CPU."""
    return BASE + off if off < PUCE2 else PUCE2_CPU + (off - PUCE2)


def lire_trad(fichiers):
    par_texte, par_adr = {}, {}
    for f in fichiers:
        for n, ligne in enumerate(open(f, encoding='utf-8'), 1):
            ligne = ligne.rstrip('\n')
            if not ligne or ligne.startswith('#') or '\t' not in ligne:
                continue
            src, fr = ligne.split('\t', 1)
            if src.startswith('@'):
                par_adr[int(src[1:], 16)] = (fr, f, n)
            else:
                par_texte[src] = (fr, f, n)
    return par_texte, par_adr


class Puce2:
    def __init__(self, rom):
        self.rom = rom
        self.pos = PUCE2 + 0x400          # 0x800000-0x8003FF réservé aux routines (ROUTINES)

    def ecrit(self, b):
        o = self.pos
        self.rom[o:o + len(b)] = b
        self.pos += len(b)
        assert self.pos < len(self.rom), 'puce 2 pleine'
        return o


def construire(rom_jp, fichiers, tout_en_saut=False, verif=False):
    import police
    rom = bytearray(rom_jp) + b'\xff' * (len(rom_jp))       # 2 -> 4 Mio
    lignes = X.catalogue(rom_jp)
    refs = dict(X.REFS)
    fiches = X.fiches(rom_jp)
    noms_fiche = {}
    # textes d'acteurs -> toutes les commandes 09/0A qui les citent (2e interpréteur)
    refs_acteur = {}
    for p_, (op_, n_) in X.analyses(rom_jp)[1].items():
        if op_ in (0x09, 0x0A):
            t_ = struct.unpack_from('<I', rom_jp, p_ + 2)[0] - BASE
            refs_acteur.setdefault(t_, []).append(p_)
    fiches_relogees = True    # tables de noms toujours déplacées (même sans traduction : validé en tout-en-saut)
    par_texte, par_adr = lire_trad(fichiers) if not tout_en_saut else ({}, {})
    erreurs, n_trad = [], 0
    p2 = Puce2(rom)

    def trad(o, b):
        """Octets à écrire pour l'entrée o (texte d'origine b), ou None si pas de traduction."""
        if tout_en_saut:
            return [bytes(b)]
        cle = T.lisible(b)
        t = par_adr.get(o) or par_texte.get(cle)
        if t is None:
            return None
        fr, f, n = t
        try:
            return [T.encode(x) for x in fr.split('{box}')]
        except T.ErreurEncodage as e:
            erreurs.append('%s:%d %06X %s' % (os.path.basename(f), n, o, e))
            return None

    if not tout_en_saut and not verif:
        police.appliquer(rom)
        import grille        # saisie du nom : minuscules / majuscules / accents (grille.py)
        grille.appliquer(rom)
    if not tout_en_saut and not verif:
        # écran-titre français (plan SCR2 recompressé ; tools/titre.py, image gfx/titre_fr.png)
        import titre
        from pathlib import Path
        t = titre.encode_title(Path(ICI) / 'gfx' / 'titre_fr.png')
        titre.patch_rom_bytes(rom, t)
        # logo japonais animé de l'intro (« ユニトロン » + sous-titre en sprites) : asset de 112
        # tuiles en 0x18078F (descripteurs 0xFF127… ; chargé en VRAM 338-449) -> tuiles vides :
        # l'intro montre le mécha seul, puis le titre français.
        a, fin = 0x18078F, 0x180C34
        n = rom_jp[a] | rom_jp[a + 1] << 8
        z = titre.compress_lzss(bytes(16 * n))
        assert len(z) <= fin - a - 2
        rom[a + 2:fin] = z + bytes(fin - a - 2 - len(z))
    if not tout_en_saut and not verif:
        for adr, avant, apres, raison in PATCHS_FENETRES:
            assert bytes(rom_jp[adr:adr + len(avant)]) == avant, (hex(adr), raison)
            rom[adr:adr + len(apres)] = apres
    if not verif:
        # routines en assembleur (tools/asm/*.asm, assemblées avec AS, cpu 96C141), zone réservée en tête de puce 2
        for org, code, patchs in ROUTINES:
            o = PUCE2 + (org - PUCE2_CPU)
            rom[o:o + len(code)] = code
            for adr, avant, apres in patchs:
                assert bytes(rom[adr:adr + len(avant)]) == avant, hex(adr)
                rom[adr:adr + len(apres)] = apres

    # --- SCRIPT / CHOIX : saut vers un bloc neuf
    an = X.analyses(rom_jp)[0]
    for t, (op, p, f) in sorted(an.textes.items()):
        b = rom_jp[t:f - 2]
        parts = trad(t, b)
        if parts is None:
            continue
        n_trad += 1
        if op == 0x13 and len(parts) > 1:
            erreurs.append('%06X {box} interdit dans une option de choix' % t); parts = [b''.join(parts)]
        if verif:
            continue
        ops = bytes(rom_jp[p:t])                     # opcode + opérandes (09 f / 13 adr3)
        bloc = bytearray()
        for k, part in enumerate(parts):
            if op == 0x09 and k < len(parts) - 1:
                bloc += bytes([0x09, 0x00])           # boîte ajoutée : attend un appui
            else:
                bloc += ops
            bloc += part + b'\xff\x00'
        r = cpu(f)
        bloc += bytes([0x02, r & 0xFF, (r >> 8) & 0xFF, (r >> 16) & 0xFF, 0x00])
        o = p2.ecrit(bytes(bloc))
        a = cpu(o)
        rom[p:p + 4] = bytes([0x02, a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF])

    # --- autres types
    deja = set()
    for o in sorted(lignes):
        typ, p, b = lignes[o]
        if typ in ('SCRIPT', 'CHOIX') or o in deja:
            continue
        if typ == 'ACTEUR':
            parts = trad(o, b)
            if parts is None:
                continue
            n_trad += 1
            if verif:
                continue
            adr = [cpu(p2.ecrit(x + b'\xff\x00')) for x in parts]
            for p_ in refs_acteur.get(o, [p]):         # TOUTES les commandes qui citent ce texte
                if len(adr) == 1 and not tout_en_saut:     # validation : tout passe par un bloc
                    rom[p_ + 2:p_ + 6] = struct.pack('<I', adr[0])
                    continue
                # {box} : « 09 f ptr » (6 o) -> « 1C ptr32 » vers un bloc « 09 f p1 … 0X f pN 1C retour »
                bloc = bytearray()
                for k, a_ in enumerate(adr):
                    opk = rom_jp[p_] if k == len(adr) - 1 else (rom_jp[p_] & 0xC0) | 0x09
                    bloc += bytes([opk, rom_jp[p_ + 1]]) + struct.pack('<I', a_)
                bloc += b'\x1c' + struct.pack('<I', cpu(p_ + 6))
                qb = p2.ecrit(bytes(bloc))
                rom[p_:p_ + 5] = b'\x1c' + struct.pack('<I', cpu(qb))
        elif typ == 'POINTE' and o in SUR_PLACE:
            # chaîne lue AUSSI par un pointeur en son milieu : traduite sur place, même longueur
            parts = trad(o, b)
            if parts is None:
                continue
            n_trad += 1
            s = b''.join(parts)
            if len(s) != len(b):
                erreurs.append('%06X SUR_PLACE : %d octets pour %d exactement (%s)' % (o, len(s), len(b), SUR_PLACE[o]))
                continue
            if not verif:
                rom[o:o + len(b)] = s
            deja.add(o)
        elif typ == 'POINTE':
            groupe = [o]
            q = o + len(b) + 2
            while q in lignes and lignes[q][0] == 'SUITE':
                groupe.append(q); q += len(lignes[q][2]) + 2
            enc = []
            for g in groupe:
                parts = trad(g, lignes[g][2])
                enc.append(parts)
            if all(x is None for x in enc):
                continue
            n_trad += sum(1 for x in enc if x is not None)
            if verif:
                deja.update(groupe)        # ses SUITE sont traitées avec elle (bug signalé au lot 25)
                continue
            neuf = bytearray()
            for g, parts in zip(groupe, enc):
                orig = bytes(lignes[g][2])
                neuf += (b''.join(parts) if parts is not None else orig) + b'\xff\x00'
                # copie de secours tronquée sur place — SEULEMENT si la chaîne d'origine suit un FF00
                # (sinon elle peut suivre du code : on n'écrit jamais au hasard)
                if parts is not None and rom_jp[g - 2] == 0xFF and rom_jp[g - 1] == 0x00:
                    s = b''.join(parts)[:len(orig)]
                    rom[g:g + len(orig) + 2] = s + b'\xff\x00' + b'\x00' * (len(orig) - len(s))
                deja.add(g)
            q = p2.ecrit(bytes(neuf))
            a = cpu(q)
            for i in refs.get(o, []):
                rom[i:i + 3] = bytes([a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF])
        elif typ == 'SUITE':
            parts = trad(o, b)           # suite orpheline (prédécesseur non POINTE) : sur place
            if parts is None:
                continue
            n_trad += 1
            s = b''.join(parts)
            if len(s) > len(b):
                erreurs.append('%06X SUITE sur place : %d octets pour %d' % (o, len(s), len(b)))
                continue
            if not verif:
                rom[o:o + len(b) + 2] = s + b'\xff\x00' + b'\x00' * (len(b) - len(s))
        elif typ == 'FICHE':
            parts = trad(o, b)
            if parts is None:
                continue
            n_trad += 1
            s = b''.join(parts)
            base, sz = fiches[o][0], fiches[o][1]
            lim = X.place_fiche(base, sz)
            if len(s) > lim:
                erreurs.append('%06X FICHE : %d car. pour %d (%s)' % (o, len(s), lim, T.lisible(b)))
                continue
            if not verif:
                if base in X.FICHES_RELOGEES:
                    noms_fiche[o] = s                     # écrit dans la table déplacée plus bas
                else:
                    rom[o:o + sz] = s + b'\xff\x00' + b'\x00' * (sz - 2 - len(s))
    # --- tables de noms déplacées (puce 2, fiches de X.NOUVELLE_TAILLE octets) : toutes les
    # fiches jusqu'au dernier nom sont recopiées (vides comprises), traduites ou non.
    if not verif and (fiches_relogees or tout_en_saut):
        nt = X.NOUVELLE_TAILLE
        for base, (p_mul, p_add) in X.FICHES_RELOGEES.items():
            sz = [s for b0, s in X.FICHES if b0 == base][0]
            n = 1 + max(k for (b0, s0, k, bb) in fiches.values() if b0 == base)
            table = bytearray()
            for k in range(n):
                o = base + k * sz
                orig = bytes(rom_jp[o:o + sz])
                if o in noms_fiche:
                    nom = noms_fiche[o]
                else:
                    i = orig.find(b'\xff\x00')
                    nom = orig[:i] if i >= 0 else b''
                table += nom + b'\xff\x00' + b'\x00' * (nt - 2 - len(nom))
            q = p2.ecrit(bytes(table))
            rom[p_mul:p_mul + 2] = struct.pack('<H', nt)
            rom[p_add:p_add + 4] = struct.pack('<I', cpu(q))
    # --- BLOC : sur place, budget partagé
    blocs = {}
    for o in sorted(lignes):
        typ, p, b = lignes[o]
        if typ == 'BLOC':
            blocs.setdefault(p, []).append(o)
    for debut, membres in blocs.items():
        budget = sum(len(lignes[m][2]) + 2 for m in membres)
        neuf = bytearray()
        touche = False
        for m in membres:
            parts = trad(m, lignes[m][2])
            if parts is not None:
                touche = True
                n_trad += 1
            neuf += (b''.join(parts) if parts is not None else bytes(lignes[m][2])) + b'\xff\x00'
        if not touche:
            continue
        if len(neuf) > budget:
            # bloc encore partiellement traduit : laissé en japonais (avertissement, pas erreur)
            AVERT.append('%06X BLOC : %d octets pour %d — laissé en japonais (raccourcir une chaîne)' % (debut, len(neuf), budget))
            continue
        if not verif:
            rom[debut:debut + budget] = bytes(neuf) + b'\x00' * (budget - len(neuf))
    return rom, n_trad, erreurs, p2.pos - PUCE2


CRC_JP = 0x84580D66


def main():
    import zlib
    a = sys.argv[1:]
    if '--tout-en-saut' in a:
        rom_jp = open(a[0], 'rb').read()
        rom, n, err, p2 = construire(rom_jp, [], True, False)
        open(a[1], 'wb').write(rom)
        print(a[1])
        return
    if '--rom' not in a:
        print(__doc__)
        sys.exit(2)
    rom_jp = open(a[a.index('--rom') + 1], 'rb').read()
    if len(rom_jp) != 0x200000 or zlib.crc32(rom_jp) != CRC_JP:
        sys.exit("ROM refusée : il faut la ROM japonaise d'origine (2 097 152 octets, CRC32 %08X)." % CRC_JP)
    code = a[a.index('--lang') + 1] if '--lang' in a else 'fr'
    racine = os.path.join(ICI, '..')
    fichiers = sorted(glob.glob(os.path.join(racine, 'lang', code, '*.txt')))
    if not fichiers:
        sys.exit('aucun fichier lang/%s/*.txt' % code)
    verif = '--verif' in a
    rom, n, err, p2 = construire(rom_jp, fichiers, False, verif)
    for e in err:
        print('ERREUR', e)
    for e in AVERT:
        print('avert.', e)
    print('%d traductions, %d erreur(s), puce 2 : 0x%X octets' % (n, len(err), p2))
    if err:
        sys.exit(1)
    if verif:
        return
    os.makedirs(os.path.join(racine, 'out'), exist_ok=True)
    sortie = os.path.join(racine, 'out', code + '.ngc')
    open(sortie + '.tmp', 'wb').write(rom)
    os.replace(sortie + '.tmp', sortie)
    print(os.path.normpath(sortie))
    if '--ips' in a:
        import ips
        patch = os.path.join(racine, 'out', code + '.ips')
        open(patch, 'wb').write(ips.fabrique(rom_jp, bytes(rom)))
        assert ips.applique(rom_jp, open(patch, 'rb').read()) == bytes(rom), 'patch IPS faux'
        print(os.path.normpath(patch), '(vérifié)')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
