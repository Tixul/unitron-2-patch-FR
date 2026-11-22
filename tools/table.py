"""Tables de caractères de Biomotor Unitron 2 : japonais (lecture) et français (écriture).

Japonais : 1 octet = 1 glyphe (FORMAT.md). FF xx = contrôle, FE xx = insertion (combat).
Français : les cases KANA sont réutilisées (le texte traduit n'en a plus besoin) :
  0x01-0x1A a-z · 0x1B.. accents et ponctuation (FR_EXTRA) · A4-BD A-Z (redessinées) · BE-C7 0-9.
Format lisible commun : {n} = FF01 (ligne), {p} = FF02 (efface la boîte), {FFxx} autres contrôles,
{J} = FF05 nom du joueur, {P} = FF06 nom du partenaire, {FExx} insertion, {xx} octet brut.
"""
import re

HIRA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
HDAKU = "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
HSMALL = "ぁぃぅぇぉゃゅょっ"
KATA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
KDAKU = "ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ"
KSMALL = "ァィゥェォャュョッ"

JP = {0x00: ' '}


def _put(t, base, s):
    for i, c in enumerate(s):
        t[base + i] = c


_put(JP, 0x01, HIRA); _put(JP, 0x2F, HDAKU); _put(JP, 0x48, HSMALL)
JP[0x52] = '。'
_put(JP, 0x53, KATA); _put(JP, 0x81, KDAKU); _put(JP, 0x9A, KSMALL)
JP[0xA3] = 'ヴ'
for i in range(26):
    JP[0xA4 + i] = chr(ord('A') + i)
for i in range(10):
    JP[0xBE + i] = chr(ord('0') + i)
# ponctuation lue sur la police (vérifiée code par code)
JP.update({0xC8: '◎', 0xC9: '【', 0xCA: '】', 0xCB: '‘', 0xCC: '’', 0xCD: '”', 0xCE: '#', 0xCF: '※',
           0xD0: '{D0}', 0xD1: '「', 0xD2: '」', 0xD3: '＊', 0xD4: '+', 0xD5: 'ー', 0xD6: '―',
           0xD7: '。', 0xD8: '/', 0xD9: '＼', 0xDA: '^', 0xDB: '_', 0xDC: ':', 0xDD: ';',
           0xDE: '<', 0xDF: '=', 0xE0: '>', 0xE1: '?', 0xE2: '★', 0xE3: '♥', 0xE4: '・',
           0xE5: '…', 0xE6: '×', 0xE7: '光', 0xE8: '闇', 0xE9: '火', 0xEA: '水', 0xEB: '木',
           0xEC: '土', 0xED: '風', 0xEE: '!', 0xEF: ',', 0xF0: '◘', 0xF1: '⌐', 0xF2: '▲',
           0xF3: '▼', 0xF4: '◀', 0xF5: '▶', 0xF6: '~'})
JP = {k: v for k, v in JP.items() if not v.startswith('{')}

# ---------------------------------------------------------------- français
FR_LOW = 'abcdefghijklmnopqrstuvwxyz'
FR_EXTRA = "éèêëàâäîïôöùûüçœÉÈÊÀÇÔÎŒ«»'-:;()….%ÂÙÛËÏÜ°ÄÖ"   # AJOUTER EN FIN seulement
FR = {' ': 0x00}
for i, c in enumerate(FR_LOW):
    FR[c] = 0x01 + i
for i, c in enumerate(FR_EXTRA):
    FR[c] = 0x1B + i
for i in range(26):
    FR[chr(ord('A') + i)] = 0xA4 + i
for i in range(10):
    FR[chr(ord('0') + i)] = 0xBE + i
# ponctuation du jeu gardée (glyphes d'origine)
FR.update({'!': 0xEE, '?': 0xE1, ',': 0xEF, '/': 0xD8, '+': 0xD4, '×': 0xE6, '#': 0xCE,
           '★': 0xE2, '♥': 0xE3, '~': 0xF6, '【': 0xC9, '】': 0xCA, '「': 0xD1, '」': 0xD2,
           '=': 0xDF, '<': 0xDE, '>': 0xE0, '·': 0xE4, '光': 0xE7, '闇': 0xE8, '火': 0xE9, '水': 0xEA,
           '木': 0xEB, '土': 0xEC, '風': 0xED, '▲': 0xF2, '▼': 0xF3, '◀': 0xF4, '▶': 0xF5})
assert max(v for v in FR.values() if v < 0x53) < 0x53

CTRL_NOM = {0x01: '{n}', 0x02: '{p}', 0x05: '{J}', 0x06: '{P}'}
CTRL_REV = {'n': 0x01, 'p': 0x02, 'J': 0x05, 'P': 0x06}


def lisible(b, table=JP):
    """Octets -> texte lisible (sans le FF00 final)."""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if c == 0xFF and i + 1 < len(b):
            out.append(CTRL_NOM.get(b[i + 1], '{FF%02X}' % b[i + 1])); i += 2; continue
        if c == 0xFE and i + 1 < len(b):
            out.append('{FE%02X}' % b[i + 1]); i += 2; continue
        ch = table.get(c)
        out.append(ch if ch is not None and ch not in '{}' else '{%02X}' % c)
        i += 1
    return ''.join(out)


_TOK = re.compile(r'\{(n|p|J|P|FF[0-9A-F]{2}|FE[0-9A-F]{2}|[0-9A-F]{2})\}')


class ErreurEncodage(Exception):
    pass


def encode(s, table=FR):
    """Texte lisible -> octets (sans FF00 final)."""
    out, i = bytearray(), 0
    while i < len(s):
        m = _TOK.match(s, i)
        if m:
            t = m.group(1)
            if t in CTRL_REV:
                out += bytes([0xFF, CTRL_REV[t]])
            elif t.startswith('FF') or t.startswith('FE'):
                out += bytes([int(t[:2], 16), int(t[2:], 16)])
            else:
                out.append(int(t, 16))
            i = m.end(); continue
        c = s[i]
        if c not in table:
            raise ErreurEncodage('caractère non encodable %r dans %r' % (c, s))
        out.append(table[c]); i += 1
    return bytes(out)


def kana(s):
    return sum(1 for c in s if '぀' <= c <= 'ヿ')
