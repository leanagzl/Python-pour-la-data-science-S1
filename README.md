# Les député.es sont-ils à l'image de leurs électeurs ?

Projet réalisé dans le cadre du cours « Python pour la data science » par Léana Ghezali et Selima Skhiri – 2026.

**Problématique :** Les député.es sont-ils représentatifs de leurs électeurs ? Nous comparons l'âge, le genre et la profession de chaque député.e aux caractéristiques socio-économiques de sa circonscription.

## Données

| Source | Contenu | Accès |
|---|---|---|
| INSEE, indicateurs par circonscription législative (2022) | 124 indicateurs socio-économiques | Fichier Excel téléchargé |
| INSEE, composition des circonscriptions | Correspondance communes - circonscriptions | Fichier Excel téléchargé |
| Députés actifs de l'Assemblée nationale | Âge, genre, profession, groupe, scores parlementaires | API data.gouv.fr |
| Contours des circonscriptions législatives (data.gouv.fr, Jérôme Desboeufs, Licence Ouverte 2.0) | Géométries pour les cartes | GeoJSON téléchargé |

Les clés de jointure entre députés, INSEE et contours sont harmonisées dans une colonne `code_circo` (5 caractères, ex. `75018`).

## Installation

```bash
git clone https://github.com/leanagzl/Python-pour-la-data-science-S1.git
cd Python-pour-la-data-science-S1
pip install -r requirements.txt
```

## Reproduire les résultats

Toutes les commandes sont à exécuter depuis la racine du dépôt, dans l'environnement Python où les dépendances sont installées.

Exécuter les étapes dans l'ordre :

```bash
# 1. Téléchargement et nettoyage des données
python -m src.collecte.lancer_extraction

# 2. Jointure entre les données des députés et les indicateurs INSEE
python -m src.traitement.jointures

# 3. Vérification des contours et génération des cinq cartes
python -m src.visualisation.cartes
```

Les cartes générées sont enregistrées dans `outputs/cartes/` :

- `carte_cadres.png`
- `carte_csp_deputes.png`
- `carte_part_femmes.png`
- `carte_genre.png`
- `carte_groupes.png`

Le rapport principal est disponible dans `rapport.ipynb`. Pour le rejouer de bout en bout, ouvrir le notebook puis sélectionner *Kernel > Restart & Run All*.

Les modules `descriptif.py`, `professions.py` et `representativite.py` fournissent les fonctions utilisées pour les analyses. Ils sont importés dans le notebook et ne se lancent pas seuls.

## Structure du projet

```text
Python-pour-la-data-science-S1/
│
├── data/
│   ├── data_brut/             # Données sources téléchargées
│   └── data_clean/            # Données nettoyées et générées
│
├── src/
│   ├── collecte/
│   │   ├── extraction_donnees.py
│   │   ├── lancer_extraction.py
│   │   └── collecte_contours.py
│   │
│   ├── traitement/
│   │   ├── jointures.py
│   │   └── professions.py
│   │
│   ├── analyse/
│   │   ├── descriptif.py
│   │   └── representativite.py
│   │
│   └── visualisation/
│       └── cartes.py
│
├── tests/
│   └── exploration.py
│
├── outputs/
│   └── cartes/                # Cartes générées
│
├── rapport.ipynb
├── README.md
├── requirements.txt
└── .gitignore
```

### Rôle des principaux modules

| Module | Rôle |
|---|---|
| `src/collecte/extraction_donnees.py` | Téléchargement, gel et nettoyage des données |
| `src/collecte/lancer_extraction.py` | Enchaîne les différentes étapes d'extraction |
| `src/collecte/collecte_contours.py` | Téléchargement et chargement des contours des circonscriptions |
| `src/traitement/jointures.py` | Jointure entre les données des députés et les indicateurs INSEE |
| `src/traitement/professions.py` | Recode les professions déclarées en catégories socioprofessionnelles |
| `src/analyse/descriptif.py` | Statistiques descriptives et graphiques |
| `src/analyse/representativite.py` | Analyses des écarts de représentativité entre députés et population |
| `src/visualisation/cartes.py` | Préparation des données géographiques et génération des cinq cartes |
| `tests/exploration.py` | Contrôle de la clé de jointure |
| `rapport.ipynb` | Rapport et analyses principales |
| `outputs/cartes/` | Images des cartes générées |
| `requirements.txt` | Dépendances Python du projet |

### Catégorisation des professions

Le module `professions.py` recode la profession déclarée des députés (colonne `job`) en catégories socioprofessionnelles comparables aux variables INSEE `act_*` : agriculteurs, artisans-commerçants-chefs d'entreprise, cadres, professions intermédiaires, employés et ouvriers. Il ajoute également les catégories `politique`, `inactif` et `non_classe`.

Le code PCS entre parenthèses est utilisé lorsqu'il existe. Sinon, des règles par mots-clés sont appliquées dans un ordre défini. Les libellés ambigus restent non classés. Le résultat est stocké dans la colonne `csp_depute`.

### Analyses de représentativité

Le module `representativite.py` compare le profil des députés à celui de leur circonscription à travers plusieurs analyses :

- Écart d'âge et corrélation de Pearson.
- Comparaison des circonscriptions des députées et des députés (test de Mann-Whitney), en métropole puis au sein de chaque groupe.
- Comparaison des catégories socioprofessionnelles des députés avec la population active pondérée.
- Part de députés cadres selon le quartile de la circonscription (test du chi²).
- Comparaison du profil des circonscriptions selon le groupe politique (test de Kruskal-Wallis, statistique H et taille d'effet epsilon carré).

## Choix de nettoyage importants

- Corse : codes `2A`/`2B` en majuscules.
- Saint-Barthélemy (`97701`) rattachée à Saint-Martin (`97801`), comme dans les données INSEE.
- Les 11 circonscriptions des Français de l'étranger n'ont pas d'indicateurs INSEE.
- Indicateurs dérivés (INSEE) : la table INSEE ne fournissant pas directement la part totale de femmes par circonscription, celle-ci est reconstruite par barycentre à partir des taux d'emploi global, masculin et féminin :

\[
\frac{actemp_{hom}-actemp}{actemp_{hom}-actemp_{fem}}\times 100
\]

### Nettoyage des données géographiques (contours)

Le fichier de contours ne suit pas le même codage que les données INSEE et Datan. Le module `cartes.py`, grâce à la fonction `ajouter_code_circo`, reconstruit la clé `code_circo`.

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

- **Contrôles :** l'exécution de `python -m src.visualisation.cartes` affiche les doublons de clé dans les contours, les contours sans INSEE et les circonscriptions INSEE sans contour. La jointure contours - table députés + INSEE est faite avec `validate="one_to_one"`, ce qui arrête le programme en cas de doublon.

- **Projections et encarts :** la métropole est tracée en Lambert-93 (EPSG:2154) et chaque territoire d'outre-mer dans sa projection UTM locale. Un encart agrandit Paris et la petite couronne (départements 75, 92, 93, 94), repérés par un cadre rouge sur la carte principale, et chaque territoire d'outre-mer présent dans les contours a son encart. L'échelle de couleurs et la légende sont communes à tous les panneaux, mais pas l'échelle géographique. Les circonscriptions sans donnée sont en gris clair.
