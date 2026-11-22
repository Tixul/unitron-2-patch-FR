"""Contrôle des fichiers de traduction SANS fabriquer la ROM.

    python tools/controle.py ROM_JP.ngc lang/<code>/*.txt [--noms-reels]

Lignes `@ADRESSE<TAB>texte` (adresse d'une entrée du catalogue, tools/extraire.py). Vérifie : adresse
connue ; caractères encodables (table.FR) ; place : 18 caractères × 2 lignes par boîte pour les dialogues
({n}{n} entre les deux lignes, {box} = boîte suivante, {p} = efface la boîte) ; {J}/{P}/{FF07} comptent 6,
{FE00}-{FE0F} (nombre) 4, {FE10}-{FE22} (nom inséré) 14 (--noms-reels : longueur réelle des noms
traduits) ; noms (FICHE) : place stricte ; codes {J} {P} {FExx} {FFxx} de l'original tous présents.
Avertit (sans erreur) quand un libellé court dépasse la longueur d'origine (menu à vérifier à l'écran).
Code de sortie 1 s'il y a une erreur.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import table as T   # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
ROM = None             # ROM japonaise (main)
LARGEUR, LIGNES = 18, 2
CODES = re.compile(r'\{(J|P|FE[0-9A-F]{2}|FF[0-9A-F]{2})\}')


NOM_PERSO = 6       # {J} {P} {FF07} : l'écran de saisie accepte 6 caractères
# largeur des noms insérés en combat ; 14 = place des fiches tant que les noms ne sont pas traduits.
# Remplacé par la longueur RÉELLE du nom FR le plus long (largeurs_noms()) quand les fiches le sont.
LARGEUR_NOMS = {}


def largeurs_noms(fichiers):
    """Longueur du nom le plus long réellement affiché, par insertion (traduit, sinon original) :
    {FE20} = ennemis (0xEBF3F) ; {FE21}/{FE22} = pièces (0xE1B12) ;
    {FE10}-{FE1F} = pièces, attaques (0xEC6E7) ou techniques (0xEF755)."""
    sys.path.insert(0, ICI)
    import extraire as X
    par_adr = {}
    for f in fichiers:
        for l in open(f, encoding='utf-8'):
            if l.startswith('@') and '\t' in l:
                s, fr = l.rstrip('\n').split('\t', 1)
                par_adr[int(s[1:], 16)] = fr
    maxi = {}
    for o, (base, sz, k, b) in X.fiches(ROM).items():
        fr = par_adr.get(o)
        n = largeur(fr) if fr is not None else len(b)
        maxi[base] = max(maxi.get(base, 0), n)
    obj, enn, att, tec = maxi.get(0xE1B12, 14), maxi.get(0xEBF3F, 14), maxi.get(0xEC6E7, 14), maxi.get(0xEF755, 14)
    out = {0x20: enn, 0x21: obj, 0x22: obj}
    for n in range(0x10, 0x20):
        out[n] = max(obj, att, tec)
    return out


def largeur(ligne):
    def rempl(m):
        c = m.group(1)
        if c in ('J', 'P', 'FF07'):
            return 'x' * NOM_PERSO          # saisie du nom : 6 caractères au plus (mesuré 21/11)
        if c.startswith('FE'):
            n = int(c[2:], 16)
            return 'x' * (4 if n < 0x10 else LARGEUR_NOMS.get(n, 14))
        return ''
    s = re.sub(r'\{(J|P|FE[0-9A-F]{2}|FF[0-9A-F]{2}|[0-9A-F]{2})\}', rempl, ligne)
    return len(s)


def charger_catalogue():
    sys.path.insert(0, ICI)
    import extraire as X
    par_txt, par_adr = collections.defaultdict(list), {}
    for o, (typ, p, b) in X.catalogue(ROM).items():
        s = T.lisible(b)
        par_txt[s].append((o, typ))
        par_adr[o] = (typ, s)
    return par_txt, par_adr


def place_fiche():
    sys.path.insert(0, ICI)
    import extraire as X
    return {o: X.place_fiche(base, sz) for o, (base, sz, k, b) in X.fiches(ROM).items()}


def controle(fichiers):
    par_txt, par_adr = charger_catalogue()
    fiches = None
    erreurs, avert = [], []
    n = 0
    for f in fichiers:
        for num, l in enumerate(open(f, encoding='utf-8'), 1):
            l = l.rstrip('\n')
            if not l or l.startswith('#') or '\t' not in l:
                continue
            src, fr = l.split('\t', 1)
            ou = '%s:%d' % (os.path.basename(f), num)
            if src.startswith('@'):
                a = int(src[1:], 16)
                if a not in par_adr:
                    erreurs.append('%s adresse inconnue %s' % (ou, src)); continue
                typ, jp = par_adr[a]
                occ = [(a, typ)]
            else:
                jp = src
                occ = par_txt.get(src)
                if not occ:
                    erreurs.append('%s ligne sans @ADRESSE' % ou); continue
            n += 1
            try:
                T.encode(fr.replace('{box}', ''))
            except T.ErreurEncodage as e:
                erreurs.append('%s %s' % (ou, e)); continue
            types = {t for a, t in occ}
            # codes du japonais présents dans le français
            cj = collections.Counter(CODES.findall(jp))
            cf = collections.Counter(CODES.findall(fr))
            if cj != cf:
                manque = cj - cf
                trop = cf - cj
                # boîte de combat avec DEUX noms insérés : l'interpellation {J}/{P} peut sauter
                # (sinon 6 + 14 + 14 cases ne tiennent jamais en 2 lignes de 18)
                noms = sum(v for k, v in cj.items() if k.startswith('FE') and int(k[2:], 16) >= 0x10)
                if noms >= 2 and not trop and set(manque) <= {'J', 'P'}:
                    manque = collections.Counter()
                if manque or trop:
                    erreurs.append('%s codes différents du japonais : manque %s, en trop %s'
                                   % (ou, dict(manque), dict(trop)))
            if '{box}' in fr and not types <= {'SCRIPT', 'ACTEUR'}:
                erreurs.append('%s {box} seulement dans les dialogues (SCRIPT, ACTEUR)' % ou)
            if 'FICHE' in types:
                if fiches is None:
                    fiches = place_fiche()
                lim = min(fiches[a] for a, t in occ if t == 'FICHE')
                if largeur(fr) > lim:
                    erreurs.append('%s FICHE : %d caractères pour %d au plus : « %s »' % (ou, largeur(fr), lim, fr))
                continue
            dialogue = '{n}' in jp or '{p}' in jp or largeur(jp) > 18 or types & {'SCRIPT', 'ACTEUR'}
            if dialogue:
                for boite in re.split(r'\{box\}|\{p\}', fr):
                    lignes = boite.split('{n}')
                    pleines = [x for x in lignes if x.strip()]
                    for x in lignes:
                        if largeur(x) > LARGEUR:
                            erreurs.append('%s ligne de %d caractères (18 au plus) : « %s »' % (ou, largeur(x), x))
                    if len(pleines) > LIGNES and not (types & {'POINTE', 'SUITE', 'BLOC'} and len([x for x in jp.split('{n}') if x.strip()]) > 2):
                        erreurs.append('%s boîte de %d lignes (2 au plus, sinon {box}) : « %s »' % (ou, len(pleines), boite))
            else:
                if largeur(fr) > max(largeur(jp), 1):
                    avert.append('%s libellé plus long que le japonais (%d > %d) : « %s » / %s'
                                 % (ou, largeur(fr), largeur(jp), fr, jp))
    return n, erreurs, avert


def main():
    global ROM
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    ROM = open(args[0], 'rb').read()
    fichiers = args[1:]
    if '--noms-reels' in sys.argv:
        LARGEUR_NOMS.update(largeurs_noms(fichiers))
    n, err, av = controle(fichiers)
    for e in err:
        print('ERREUR', e)
    for a in av:
        print('avert.', a)
    print('%d lignes, %d erreur(s), %d avertissement(s)' % (n, len(err), len(av)))
    sys.exit(1 if err else 0)


if __name__ == '__main__':
    main()
