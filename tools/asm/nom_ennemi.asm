; Nom de l'ennemi pour l'insertion {FE20} des messages de combat — noms d'ennemis allongés (VF).
;
; Le jeu recopie le nom (table 0xEBF3F, fiches de 10 octets) dans un tampon RAM de 10 octets
; (0x60A9, ldir BC=10 en 0x212646) ; {FE20} (gestionnaire 0x213325) affiche ce tampon. La VF
; déplace la table en fiches de 16 octets (14 caractères) : le tampon ne reçoit plus que les
; 10 premiers octets, sans FF00. Le même tampon sert aussi au nom de l'ADVERSAIRE en duel par
; câble (0x215610, 8 octets depuis 0x4F08).
; Cette routine remplace « ld XHL,0x60A9 » du gestionnaire : si les 8 premiers octets du tampon
; sont ceux du nom de l'ennemi courant (index 0x60A6, routine 0x20B2F3) -> nom COMPLET en ROM ;
; sinon (câble) -> le tampon, comme avant. Puis elle continue en 0x213368 (copie du nom).
; Entrée/sortie comme 0x213368 : XDE = destination (conservé), XHL = source.
;
; Assemblage : asl -cpu 96C141 nom_ennemi.asm ; p2bin nom_ennemi.p  (build.py intègre les octets)

        cpu     96C141
        maxmode on
        org     800100h

NOM_ENNEMI:
        push    xde
        push    xbc
        ld      xhl,0
        ld      l,(60A6h)
        call    20B2F3h         ; XHL = nom de l'ennemi dans la table (déplacée)
        ld      xbc,xhl
        ld      xde,60A9h
        ld      w,8
BOUCLE: ld      a,(xbc+)
        cp      a,(xde+)
        jr      nz,TAMPON
        djnz    w,BOUCLE
        jr      FIN             ; identique : XHL = nom complet
TAMPON: ld      xhl,60A9h       ; différent (câble) : le tampon
FIN:    pop     xbc
        pop     xde
        jp      213368h
