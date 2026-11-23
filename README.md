# Python pour la data science : députés et circonscriptions

Projet réalisé par Leana Ghezali et Selima Skhiri

**Problématique :** Les députés sont-ils représentatifs de leurs électeurs ? Nous comparons l'âge, le genre, la profession et le groupe politique de chaque député aux caractéristiques socio-économiques de sa circonscription.

## Données

| Source | Contenu | Accès |
|---|---|---|
| INSEE, indicateurs par circonscription législative (2022) | 124 indicateurs socio-économiques | Fichier Excel téléchargé |
| INSEE, composition des circonscriptions | Correspondance communes - circonscriptions | Fichier Excel téléchargé |
| Députés actifs de l'Assemblée nationale | Âge, genre, profession, groupe, scores parlementaires | API data.gouv.fr |
| Contours des circonscriptions législatives (data.gouv.fr, Jérôme Desboeufs, Licence Ouverte 2.0) | Géométries pour les cartes | GeoJSON téléchargé |

Les clés de jointure entre députés, INSEE et contours sont harmonisées dans une colonne `code_circo` (5 caractères, ex. `75018`).

## Installation

    git clone https://github.com/leanagzl/Python-pour-la-data-science-S1.git
    cd Python-pour-la-data-science-S1
    pip install -r requirements.txt

## Reproduire les résultats

À exécuter dans cet ordre, depuis la racine du dépôt :

    python lancer_extraction.py   # télécharge et nettoie les données (dossier data/)
    python jointures.py           # joint députés et indicateurs INSEE
    python cartes.py              # télécharge les contours si besoin, vérifie les clés,
                                  # produit carte_cadres.png, carte_csp_deputes.png,
                                  # carte_part_femmes.png, carte_genre.png, carte_groupes.png

Le rapport est dans `rapport.ipynb` (menu *Kernel > Restart & Run All* pour le rejouer de bout en bout). Les modules `descriptif.py`, `professions.py` et `representativite.py` fournissent les fonctions d'analyse et ne se lancent pas seuls : ils supposent que les tables nettoyées produites par les trois commandes ci-dessus existent.

## Structure du projet

| Fichier | Rôle |
|---|---|
| `extraction_donnees.py` | Téléchargement, gel et nettoyage des données |
| `lancer_extraction.py` | Enchaîne les étapes d'extraction |
| `jointures.py` | Jointure députés - indicateurs INSEE |
| `descriptif.py` | Statistiques descriptives et graphiques |
| `professions.py` | Recode la profession déclarée des députés (colonne `job`) en catégories socioprofessionnelles comparables aux variables INSEE `act_*` (agriculteurs, artisans-commerçants-chefs d'entreprise, cadres, professions intermédiaires, employés, ouvriers) plus `politique`, `inactif` et `non_classe`. Utilise le code PCS entre parenthèses quand il existe, sinon des règles par mots-clés appliquées dans l'ordre ; les libellés ambigus restent non classés. Produit la colonne `csp_depute` |
| `representativite.py` | Compare le profil des députés à celui de leur circonscription : écart d'âge et corrélation (Pearson), circonscriptions des députées et des députés (Mann-Whitney, en métropole puis à l'intérieur de chaque groupe), catégories socioprofessionnelles des députés contre population active pondérée, part de députés cadres selon le quartile de la circonscription (chi2), profil des circonscriptions par groupe politique (Kruskal-Wallis, avec statistique H et taille d'effet epsilon carré) |
| `rapport.ipynb` | Rapport |
| `exploration.py` | Contrôle de la clé de jointure |
| `collecte_contours.py` | Téléchargement des contours des circonscriptions (gelés dans `data/data_brut/contours_circonscriptions.geojson`, pas de nouveau téléchargement s'il existe) et chargement en GeoDataFrame |
| `cartes.py` | Construit `code_circo` pour les contours, les joint aux députés et aux indicateurs INSEE, puis dessine cinq cartes (part de cadres, CSP des députés, part de femmes dans la population, genre du député, groupe du député) avec des encarts pour Paris et la petite couronne et pour l'outre-mer |
| `requirements.txt` | Dépendances Python |

## Choix de nettoyage importants

- Corse : codes `2A`/`2B` en majuscules.
- Saint-Barthélemy (`97701`) rattachée à Saint-Martin (`97801`), comme dans les données INSEE.
- Les 11 circonscriptions des Français de l'étranger n'ont pas d'indicateurs INSEE.
- Indicateurs dérivés (INSEE) : la table INSEE ne fournissant pas directement la part totale de femmes par circonscription, celle-ci est reconstruite par barycentre à partir des taux d'emploi global, masculin et féminin : $(actemp_{hom} - actemp) / (actemp_{hom} - actemp_{fem}) \times 100$.

### Nettoyage des données géographiques (contours)

Le fichier de contours ne suit pas le même codage que les données INSEE et Datan. `cartes.py` (fonction `ajouter_code_circo`) reconstruit la clé `code_circo` :

- **Format de la clé :** département et circonscription, soit 5 caractères. En métropole, département sur 2 caractères et circonscription sur 3 (`75018`, `2A001`). En outre-mer, département sur 3 caractères et circonscription sur 2 (`97101`). Le numéro de circonscription est lu dans les deux derniers caractères de `codeCirconscription`.
- **Traduction des codes `ZA`/`ZB`... :** le fichier de contours désigne l'outre-mer par des préfixes en `Z` que nous traduisons en codes départementaux :

  | Contours | Code département | Territoire |
  |---|---|---|
  | `ZA` | `971` | Guadeloupe |
  | `ZB` | `972` | Martinique |
  | `ZC` | `973` | Guyane |
  | `ZD` | `974` | La Réunion |
  | `ZS` | `975` | Saint-Pierre-et-Miquelon |
  | `ZM` | `976` | Mayotte |

- **Sept circonscriptions sans contour :** Saint-Martin/Saint-Barthélemy (1), Wallis-et-Futuna (1), Polynésie française (3) et Nouvelle-Calédonie (2), soit les départements `977`/`978`, `986`, `987` et `988`. Elles ne figurent pas dans le fichier de contours et sont absentes des cartes, sans qu'on ait cherché à les approximer. Les 11 circonscriptions des Français de l'étranger ne sont pas non plus cartographiées.
- **Contrôles :** `python cartes.py` affiche les doublons de clé dans les contours, les contours sans INSEE et les circonscriptions INSEE sans contour. La jointure contours - table députés + INSEE est faite avec `validate="one_to_one"`, ce qui arrête le programme en cas de doublon.
- **Projections et encarts :** la métropole est tracée en Lambert-93 (EPSG:2154) et chaque territoire d'outre-mer dans sa projection UTM locale. Un encart agrandit Paris et la petite couronne (départements 75, 92, 93, 94), repérés par un cadre rouge sur la carte principale, et chaque territoire d'outre-mer présent dans les contours a son encart. L'échelle de couleurs et la légende sont communes à tous les panneaux, mais pas l'échelle géographique. Les circonscriptions sans donnée sont en gris clair.