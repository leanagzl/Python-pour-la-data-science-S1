from extraction_donnees import (
    gel_donnees_insee,
    gel_donnees_deputes,
    gel_bases_clean,
    charger_donnees,
)

gel_donnees_insee()
gel_donnees_deputes()
gel_bases_clean()

deputes, insee_indic, insee_compo, dico_insee = charger_donnees()

print(deputes.shape)
print(insee_indic.shape)
print(insee_compo.shape)