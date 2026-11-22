# Biomotor Unitron 2 (Kikou Seiki Unitron) — notes techniques (ROM, scripts, texte, interface)

Tout ce qui suit a été mesuré sur la ROM japonaise d'origine (2 Mio, CRC32 `84580D66`). Adresses CPU :
la cartouche commence en 0x200000 (fichier 0 = CPU 0x200000) ; la 2e puce de la ROM traduite
(fichier 0x200000) est vue en CPU 0x800000. Les adresses des fichiers `lang/` sont des adresses
**fichier**.

## Chaîne de construction
`tools/build.py` : ROM japonaise → catalogue du texte (`extraire.py`) → police latine (`police.py`) →
grille de saisie du nom (`grille.py`) → écran titre (`titre.py`) → fenêtres élargies → routine
NOM_ENNEMI → textes relogés en 2e puce → tables de noms agrandies → ROM de **4 Mio** → patch IPS
**depuis la ROM japonaise**. 0x800000-0x8003FF est réservé aux routines ; le texte commence en 0x800400.

## Codes du texte
1 octet = 1 caractère (kana, A-Z en 0xA4-0xBD, chiffres 0xBE-0xC7, ponctuation et kanji d'éléments
0xC8-0xF6). Moteur d'affichage 0x20A1C3 : 1 caractère = 1 tuile 8×8 (chasse fixe), texte **coupé** à la
largeur de la fenêtre.
- `FF00` fin · `FF01` ligne (`{n}` ; dans les boîtes, deux lignes séparées par `FF01 FF01`) ·
  `FF02` efface la boîte (`{p}`) · `FF03`/`FF04` drapeaux d'affichage · `FF05` nom du pilote (RAM
  0x4FD5, `{J}`) · `FF06` nom du partenaire (0x4FDE, `{P}`) · `FF07` nom de l'Elel (0x4FE8).
  Les noms font 6 caractères au plus (saisie : longueur en 0x6592).
- Combat : gabarits développés par 0x2131F6 dans le tampon 0x4000 ; `FE xx` = insertion : 00-0F nombre,
  10-1F chaîne (pointeur posé par l'appelant), 20 nom de l'ennemi, 21/22 noms par index (table 0x21323E).

## Script des événements (scènes)
Interpréteur 0x213895, table de sauts 0x2138B8, 36 commandes, adresses de script sur 3 octets ; entrée
par `call 0x2137F6` avec XHL = script. Opérandes : 00 — · 01 1 + retour · **02 adr3 saut** · 03 adr3
appel · 04 3 · 05/06 1 · 07/08 1+adr3 (saut conditionnel) · **09 f + texte jusqu'à FF00** (f = 0 :
attendre un bouton) · 0A/0B 2 · 0C-12 1 · **13 adr3 + texte** (entrée de choix) · 14 adr3 · 15-17 2 ·
18-1A 2+adr3 · 1B 2 · 1C table d'adr3 (index 2·[0x4FE6]+[0x4FE7]) · 1D 1 · 1E — · 1F 1 (oui/non) · 20 2 ·
21 adr4 · 22 4 · 23 —. Portraits : commande `11 xx` (00 narration, 04 partenaire, 19 Thomas…).

## Script des acteurs (personnages et objets)
Second interpréteur : boucle 0x228C0E, table 0x228C2E, 49 commandes, pointeurs 32 bits.
⚠ opcode = octet & 0x3F (le décalage `sll 2,A` se fait sur 8 bits). Textes : `09 f ptr32` (ouvre la
fenêtre f, pose le texte, **suspend l'acteur** jusqu'à la fin, retenue mise) et `0A f ptr32` (écrit sans
attendre). `1C ptr32` = saut. `1D` = aiguillage sur une table en ligne (index 2·[0x4FE6]+[0x4FE7]) ;
`1D`/`1E`/`27` ne retombent sur la suite que si un pointeur est nul. Fenêtres d'acteur : 18 × 2.

## Catalogue (`tools/extraire.py`)
- **SCRIPT / CHOIX** : parcours complet du script des événements (entrées directes, puis toute cible de
  pointeur 3 octets dont le parcours est propre, hors scripts d'acteurs).
- **ACTEUR** : parcours du second interpréteur depuis les cibles de pointeurs 32 bits.
- **FICHE** : tables de noms `base + (i-1)·taille`, nom calé à gauche + FF00 : éléments 0x12F8B (×5),
  pièces et objets 0xE1B12 (×8), ennemis 0xEBF3F (×10), attaques 0xEC6E7 (×10), techniques 0xEF755 (×8).
- **POINTE** : chaînes citées par un pointeur « fort » : chargé par du code (`ld rr,imm32` = 40-47 …
  00, ou `lda rr,(adr24)` = F2 … 30-37) ou membre d'une table (un autre pointeur de texte à ±3..±16
  octets, **qui ne soit pas lui-même chargé par du code** : sinon des opérandes d'instructions voisines
  passent pour des pointeurs). Sources cherchées seulement dans le code et les données de texte
  (`ZONES_SOURCES`). **SUITE** = chaîne lue juste après une POINTE.
- **BLOC** : chaînes lues « n-ième chaîne » d'un bloc, sans pointeur propre : traduites sur place, le bloc
  garde sa taille (budget partagé). 0x1FCFA-0x2043B est un doublon jamais lu de 0x16EC2-0x17603.
- `FORCER` / `EXCLURE` : débuts de texte vérifiés à l'écran (texte collé derrière du code, tables de
  pointeurs prises pour du texte, comme 0x20DE9 et 0x20D54 devant les titres de la saisie du nom).

## Allonger le texte sans reconstruire les scripts
- Événements : `09 f texte FF00` → `02 adr3` vers un bloc en 2e puce
  `09 f … FF00 [09 00 … FF00] 02 retour` ; autant de boîtes que nécessaire (`{box}`).
- Acteurs : pointeur 32 bits réécrit ; avec `{box}`, la commande `09/0A f ptr32` (6 octets) de **chaque**
  commande qui cite le texte devient `1C ptr32` vers `09 f p1 … [commande d'origine] f pN 1C retour`.
- Chaînes pointées : chaîne + suites copiées en 2e puce, tous les pointeurs forts réécrits ; une copie
  de secours tronquée reste sur place si la chaîne d'origine suit un FF00. Chaînes aussi lues par un
  pointeur **en leur milieu** (`SUR_PLACE`, ex. titre de l'écran des fichiers 0x14630) : traduites sur
  place, même longueur exacte.
- Noms : les tables pièces, attaques et techniques sont déplacées en fiches de **16 octets
  (14 caractères)** (patch de l'imm16 du `mul` et de l'imm32 de l'`add` de leur routine d'accès,
  `FICHES_RELOGEES`). Ennemis : 0x212646 recopie le nom dans un tampon RAM de 10 octets (0x60A9, aussi
  utilisé pour l'adversaire au câble) ; la routine **NOM_ENNEMI** (`tools/asm/nom_ennemi.asm`, CPU
  0x800100, appelée par le gestionnaire `{FE20}` 0x213325) lit le nom complet dans la table si le
  tampon en contient le début, sinon le tampon.
- Validation : `build.py ROM OUT --tout-en-saut` fait passer **tout** le texte par ces mécanismes avec
  le japonais d'origine ; comparé à la ROM japonaise complétée à 4 Mio : identique image par image
  (allumage → prologue → combat → donjon, options, aide).

## Police
Lecteur 0x20A1EB ; glyphe du code c en fichier **0x2C702 + 16·c**, 8×8, 2 bits par pixel (encre 1,
fond 3), non compressée ; une seule police pour tout le jeu. Le texte traduit n'utilise plus les kana :
a-z en 0x01-0x1A, puis `FR_EXTRA` (accents, ponctuation, Ä Ö) à partir de 0x1B ; A-Z (0xA4-0xBD)
redessinées ; chiffres et ponctuation d'origine gardés (`!` 0xEE, `?` 0xE1, `,` 0xEF, éléments
0xE7-0xED). Majuscules accentuées : la lettre sur 6 lignes (une ligne en double retirée, jamais la barre
du E ou du A), l'accent sur les 2 premières.

## Fenêtres
Création 0x209FA4 (A = n°, C = largeur, B = hauteur, HL = 1re tuile), position 0x20A055 (C = colonne,
B = rangée ; B ≥ 32 = plan SCR2, qui défile de (0x49E4, 0x49E6)). Les tuiles du cadre sont fixes en
0x1F5-0x1FE : la fenêtre 3 (base 0x1B8) a 61 tuiles au plus. Fenêtres modifiées (`PATCHS_FENETRES`) :
- liste d'armes en combat : largeur 8 → 12 (10 caractères), défilement X 0xB0 → 0xD0, curseur
  `ld BC,0x0060` (0x20BFCB) → 0x40 ;
- options, effacement des données : curseur x = n·0x20 + 0x50 → n·0x38 + 0x38 (0x214D55).
Le menu de commandes de combat (fenêtre 3, 9 rangées) ne peut pas être élargi : libellés de 6 caractères.

## Saisie du nom (`tools/grille.py`)
Table 0x20F7B (CPU 0x220F7B + 8·n, n en 0x6591) : 130 cases de 8 octets = code en mode 1 (ひらがな),
code en mode 2 (カタカナ), colonne, rangée, puis les n° des 4 cases voisines (direction 0-3, lue en +4
par 0x22144F) ; mode en 0x6590 (0 = premier code) ; ajout d'une lettre 0x22148F, effacement 0x2214AF.
Libellés (colonne 15, 5 caractères) : actions 0-3 (mode 1, mode 2, effacer, valider). La grille française
garde voisins et positions et ne change que les deux codes de chaque case : minuscules / majuscules en
haut, accents de l'autre casse en bas à gauche, A-Z 0-9 en bas à droite.

## Écran titre
Descripteurs d'images en 0xFF0F0+ (pointeurs 3 octets : carte, tuiles n16 + LZSS, palettes).
Titre (plan SCR2) : 0x17FB42 / 0x17FE5A / 0x18048F, réencodé depuis `tools/gfx/titre_fr.png` par
`titre.py`. Le logo japonais animé de l'intro (0x18078F, 112 tuiles en sprites) est remplacé par des
tuiles vides : l'intro montre le mécha seul, puis le titre latin.
