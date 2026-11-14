# Python-pour-la-data-science-S1

from extraction_donnees import (
    gel_donnees_insee,
    gel_donnees_deputes,
    gel_bases_clean,
    charger_donnees,
)

# 1. À lancer une fois pour télécharger et nettoyer les données
gel_donnees_insee()
gel_donnees_deputes()
gel_bases_clean()

# 2. Chargement direct des 4 tables propres pour travailler sur tes jointures
deputes, insee_indic, insee_compo, dico_insee = charger_donnees()