"""Grille de l'écran de saisie du nom, refaite pour le français (21/11).

Table du jeu : CPU 0x220F7B + 8·n, 130 cases de 8 octets : code mode 1 (ひらがな), code mode 2
  (カタカナ), colonne, rangée, n° des 4 cases voisines. Ici on lit par pas de 8 depuis 0x20F77 (4 octets
  plus tôt) : codes en +4/+5, colonne en +6, rangée en +7 — mêmes octets.
On ne touche ni aux voisins ni aux positions : seulement les deux codes de chaque case.
Mode 1 = minuscules, mode 2 = majuscules (libellés « abc » / « ABC »).
  rangées 1-5, colonnes 1-12 (en haut)  : lettres de la casse du mode + accents + signes
  rangées 7-11, colonnes 1-5 (bas gauche) : les accents de L'AUTRE casse (les deux toujours à portée)
  rangée 12, colonnes 1-5               : - · . ! ?
  colonnes 7-12, rangées 7-12            : A-Z 0-9 (inchangé)
Les 4 libellés (colonne 15) gardent leurs codes d'action.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import table as T   # noqa: E402

BASE, N = 0x20F77, 130

HAUT_MIN = "abcdefghijklmnopqrstuvwxyzéèêëàâäîïôöùûüçœ'-.!?,:;()«»…%°★♥~"
HAUT_MAJ = "ABCDEFGHIJKLMNOPQRSTUVWXYZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇŒ'-.!?,:;()«»…%°★♥~"
BAS_MAJ = "ÉÈÊËÀÂÄÎÏÔÖÙÛÜÇŒ+/=#<>×♥★"
BAS_MIN = "éèêëàâäîïôöùûüçœ+/=#<>×♥★"
SIGNES = "-·.!?"


def cases(rom):
    out = {}
    for i in range(N):
        o = BASE + 8 * i
        out[(rom[o + 6], rom[o + 7])] = o
    return out


def appliquer(rom):
    c = cases(rom)
    assert len(HAUT_MIN) == len(HAUT_MAJ) == 60 and len(BAS_MAJ) == len(BAS_MIN) == 25
    k = 0
    for col in range(1, 13):
        for rang in range(1, 6):
            o = c[(col, rang)]
            rom[o + 4], rom[o + 5] = T.FR[HAUT_MIN[k]], T.FR[HAUT_MAJ[k]]
            k += 1
    k = 0
    for col in range(1, 6):
        for rang in range(7, 12):
            o = c[(col, rang)]
            rom[o + 4], rom[o + 5] = T.FR[BAS_MAJ[k]], T.FR[BAS_MIN[k]]
            k += 1
        o = c[(col, 12)]
        rom[o + 4] = rom[o + 5] = T.FR[SIGNES[col - 1]]
    return k
