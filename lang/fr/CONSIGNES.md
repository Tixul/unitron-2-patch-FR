# Biomotor Unitron 2 (Kikou Seiki Unitron) — consignes de traduction française

Jeu : RPG de robots (Yumekobo/SNK, Neo Geo Pocket Color, 2000). Le héros pilote un Unitron (robot géant
biomécanique), explore des donjons, développe des pièces, combat. Ton : aventure fantasy-mécanique,
chaleureuse, avec de l'humour ; personnages hauts en couleur (mécanicien bourru, enfant fan de robots,
fille-chat…). Public : joueurs français d'aujourd'hui. **Qualité attendue = une vraie VF commerciale.**

## 1. ADAPTER, pas traduire (règle n° 1)
- Chaque boîte doit avoir du sens SEULE, dite par CE personnage, comme un Français le dirait à l'oral.
- Se demander ce que le personnage VEUT DIRE, puis l'écrire naturellement. Pas de calque, pas d'ordre
  des mots « traduit ». Relire chaque ligne : « un natif le dirait-il ? », pas seulement « c'est correct ».
- Gags, tics, jeux de mots : trouver un équivalent français qui garde la FONCTION de la réplique.
- Le japonais est tout en kana (pas de kanji) : bien découper les mots, lire le contexte des lignes
  voisines (le lot suit l'ordre des scènes).
- Les « …… » et silences japonais : les garder quand ils portent une émotion, les alléger sinon
  (« ………{n}{n}…Ah, quand même! »).

## 2. Contraintes techniques (vérifiées par `tools/controle.py` : une erreur = refusé)
- Police à chasse fixe : **1 caractère = 1 case**. Boîte de dialogue : **18 caractères × 2 lignes**.
  Les deux lignes sont séparées par `{n}{n}` (ligne vide entre elles, comme le japonais).
- `{box}` = **boîte suivante** (scènes et personnages : fichiers fr_10 et fr_20). On peut ALLONGER : mieux vaut 2 boîtes
  naturelles qu'une boîte télégraphique. Ne pas en abuser non plus (rythme de lecture).
- `{p}` = efface la boîte (début des messages de combat/menus) : le recopier à la même place.
- Colonne « place » : `18x2` = dialogue ; `Nc` = libellé court de N caractères (menus, noms : si le
  français ne tient vraiment pas, vérifier à l'écran ; une fenêtre peut parfois être élargie,
  voir PATCHS_FENETRES dans tools/build.py) ; FICHE = place STRICTE (nom dans une table à taille fixe) ; `bloc` = garder à
  peu près la longueur du japonais.
- Majuscules ET minuscules, avec accents : é è ê ë à â ä î ï ô ö ù û ü ç œ É È Ê À Ç Ô Î Œ Â Ù Û Ë Ï Ü, et °.
- Ponctuation : `. , ; : ! ? - ' … ( ) « » % / +` · `【 】` (affichés comme des crochets : le jeu
  s'en sert pour les noms propres, lieux et termes clés — les garder quand le japonais les a).
- **Pas d'espace avant ! ? : ;** (la place est comptée).
- Codes à RECOPIER tels quels (leur position dans la phrase est libre) :
  `{J}` = nom du héros (compte **6** cases : la saisie accepte 6 lettres), `{P}` = nom de la partenaire (6),
  `{FE00}`…`{FE0F}` = un NOMBRE inséré (4 cases), `{FE10}`…`{FE1F}` = un NOM inséré (objet,
  technique : jusqu'à 14 cases), `{FE20}` = nom de l'ennemi (14), `{FE21}`/`{FE22}` = nom d'attaque (14) :
  une ligne qui contient un nom inséré doit en général lui être réservée (« {FE20}{n}{n}est vaincu! »),
  `{FF07}` = nom (familier, 6), `{FF03}`/`{FF04}` = codes d'affichage.
  Les messages à insertion (combat surtout) doivent se lire juste UNE FOIS L'INSERTION FAITE :
  « {p}{J} a vaincu{n}{n}{FE20}! » et non un ordre japonais.

## 3. Le héros, la partenaire, les personnages
- **Le héros `{J}`** (nom choisi par le joueur : JESS par défaut, NINA, AXEL…) peut être un garçon OU
  une fille : **toute phrase qui parle du héros doit rester épicène** (pas d'accord au masculin ou au
  féminin : « Tu as l'air en forme » et non « Tu es prêt »). C'est NON négociable.
- **La partenaire `{P}`** (portrait 04) = l'enfant de Thomas, choisie par le joueur parmi 10 caractères.
  Ses répliques existent en **10 variantes**, toujours dans cet ordre, chacune avec sa voix :
  1. garçon franc et sympa (おれ, « よろしくな! ») — 2. fille enjouée (わたし…よ, « {J}さん ») —
  3. garçon froid et laconique (« …わたしのなまえは{P}だ ») — 4. jeune femme posée, douce (わたし…よ,
  « はじめまして ») — 5. garçon bourru, gouailleur (オレ, « そんで », « すっげぇ ») —
  6. fille-chat (« にゃ » « にょ » : la rendre avec un tic français cohérent, ex. finales en « -nya »,
  retenu : « nya », gardé partout) — 7. jeune homme très poli (« ですよ »,
  « とうさん » : vouvoie son père) — 8. fille piquante (アタシ, « むっ! », « わよ ») —
  9. garçon doux (ぼく, « だよ ») — 10. petite fille timide (« パパ », « ……です »).
  Chaque variante garde SA voix d'un bout à l'autre du jeu. **Genre (prouvé par « むすこ ») :
  les variantes IMPAIRES (1, 3, 5, 7, 9) sont des GARÇONS (fils de Thomas), les PAIRES (2, 4, 6, 8, 10)
  des FILLES** — la 3 est donc un garçon froid et laconique. Comment ils appellent Thomas : 1, 2, 6, 8, 9,
  10 « papa » ; 3, 4 « Père » ; 5 « le vieux » ; 7 « Père » en le VOUVOYANT.
  ⚠ Le portrait 04 n'est pas toujours la partenaire (Faina/Myun ailleurs ; mode câble = 0E) : suivre le sens.
  Tous tutoient le héros, sauf indication contraire du japonais.
- **Thomas Orbit** (トマス・オービット, portrait 19) : mécanicien de l'【atelier Orbit】, bourru et
  généreux, parle cash (« おめぇ », « ガキ ») : familier, oral, jamais vulgaire au-delà de « foutu ».
- **Sirius est une FEMME** (ménestrelle, vouvoie). Les autres personnages (Solty, Arkis, Satella, Sayaka…) : déduire la voix du japonais
  (わたくし = très poli, やで/やん = parler de l'Ouest → accent chantant/gouailleur, etc.) et la noter
  dans le glossaire.
- Tutoiement par défaut entre jeunes ; vouvoiement pour les adultes polis, les inconnus, les
  personnages qui parlent en です/ます à quelqu'un qu'ils ne connaissent pas.
- Narration (portrait 00, 1E) : passé simple, sobre.

## 4. Noms et termes : voir GLOSSAIRE.md (À RESPECTER). Tout terme nouveau récurrent : le proposer
dans le glossaire (japonais → français choisi).

## 5. Format des fichiers
`lang/fr/*.txt`, une ligne par texte : `@ADRESSE<TAB>français` (adresse de l'entrée dans
`out/catalogue.tsv`, produit par `tools/extraire.py` depuis votre ROM). Contrôle avant de fabriquer :
    python tools/controle.py ROM_JP.ngc lang/fr/*.txt      → 0 erreur exigé.
