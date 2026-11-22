"""Patch IPS (records RLE pour les longues répétitions).

    python tools/ips.py apply ROM_JP.ngc PATCH.ips SORTIE.ngc     appliquer un patch
    python tools/ips.py make  ROM_JP.ngc ROM_FR.ngc SORTIE.ips    fabriquer un patch (revérifié)
"""
import os
import sys

MAX = 0xFFFF


def fabrique(a, b):
    a = a + bytes(len(b) - len(a)) if len(a) < len(b) else a
    out = bytearray(b'PATCH')
    i = 0
    while i < len(b):
        if a[i] == b[i] and i < len(a):
            i += 1
            continue
        j = i
        while j < len(b) and j - i < MAX and (a[j] != b[j] or (j + 1 < len(b) and a[j + 1] != b[j + 1])):
            j += 1
        if i == 0x454F46:                     # « EOF » : décaler d'un octet
            i -= 1
        k = i
        while k < j:                          # répétitions (remplissage 0xFF de la puce 2) -> RLE
            r = k
            while r < len(b) and r - k < MAX and b[r] == b[k] and (r < j or a[r] != b[r]):
                r += 1
            if r - k >= 16:
                out += k.to_bytes(3, 'big') + b'\0\0' + (r - k).to_bytes(2, 'big') + b[k:k + 1]
                k = r
                j = max(j, r)
                continue
            e = k
            while e < j and e - k < MAX:
                if e + 16 <= len(b) and b[e:e + 16] == b[e:e + 1] * 16:
                    break
                e += 1
            e = max(e, k + 1)
            out += k.to_bytes(3, 'big') + (e - k).to_bytes(2, 'big') + b[k:e]
            k = e
        i = j
    return bytes(out + b'EOF')


def applique(a, p):
    r = bytearray(a)
    k = 5
    while p[k:k + 3] != b'EOF':
        o = int.from_bytes(p[k:k + 3], 'big')
        n = int.from_bytes(p[k + 3:k + 5], 'big')
        k += 5
        if n == 0:
            n = int.from_bytes(p[k:k + 2], 'big')
            data = p[k + 2:k + 3] * n
            k += 3
        else:
            data = p[k:k + n]
            k += n
        if len(r) < o + n:
            r += bytes(o + n - len(r))
        r[o:o + n] = data
    return bytes(r)


def main():
    if len(sys.argv) != 5 or sys.argv[1] not in ('apply', 'make'):
        raise SystemExit(__doc__)
    cmd, src, x, sortie = sys.argv[1:5]
    a = open(src, 'rb').read()
    if cmd == 'apply':
        res = applique(a, open(x, 'rb').read())
    else:
        b = open(x, 'rb').read()
        res = fabrique(a, b)
        if applique(a, res) != b:
            raise SystemExit('ERREUR : le patch ne redonne pas la ROM visée')
    tmp = sortie + '.tmp'
    open(tmp, 'wb').write(res)
    os.replace(tmp, sortie)
    print('%s : %d octets' % (sortie, len(res)))


if __name__ == '__main__':
    main()
