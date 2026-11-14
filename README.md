# Python pour la data science : députés et circonscriptions

Projet réalisé par Leana Ghezali et Selima Skhiri

**Problématique :** Les députés représentent-ils bien leurs circonscriptions ? Nous comparons l'âge, le genre, la profession et le groupe politique de chaque député aux caractéristiques socio-économiques de sa circonscription.

## Données

| Source | Contenu | Accès |
|---|---|---|
| INSEE, indicateurs par circonscription législative (2022) | 124 indicateurs socio-économiques | Fichier Excel téléchargé |
| INSEE, composition des circonscriptions | Correspondance communes - circonscriptions | Fichier Excel téléchargé |
| Députés actifs de l'Assemblée nationale | Âge, genre, groupe, scores parlementaires | API data.gouv.fr |

Les clés de jointure entre députés et INSEE sont harmonisées dans une colonne `code_circo` (5 caractères, ex. `75018`).

## Installation

```bash
git clone https://github.com/leanagzl/Python-pour-la-data-science-S1.git
cd Python-pour-la-data-science-S1
pip install -r requirements.txt
```

## Reproduire les résultats

```bash
python lancer_extraction.py   # télécharge et nettoie les données (dossier data/)
python jointures.py           # joint députés et indicateurs INSEE
```

Le rapport est dans `rapport.ipynb`.

## Structure du projet

| Fichier | Rôle |
|---|---|
| `extraction_donnees.py` | Téléchargement, gel et nettoyage des données |
| `lancer_extraction.py` | Enchaîne les étapes d'extraction |
| `jointures.py` | Jointure députés - indicateurs INSEE |
| `descriptif.py` | Statistiques descriptives et graphiques |
| `rapport.ipynb` | Rapport |
| `exploration.py` | Contrôle de la clé de jointure |

## Choix de nettoyage importants

- Corse : codes `2A`/`2B` en majuscules.
- Saint-Barthélemy (`97701`) rattachée à Saint-Martin (`97801`), comme dans les données INSEE.
- Les 11 circonscriptions des Français de l'étranger n'ont pas d'indicateurs INSEE.