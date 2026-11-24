"""
Récupération des contours géographiques des circonscriptions législatives
(data.gouv.fr, producteur : Jérôme Desboeufs, Licence Ouverte 2.0).
"""

import geopandas as gpd
import requests

from src.collecte.extraction_donnees import DATA_DIR, HEADERS

URL_CONTOURS = (
    "https://www.data.gouv.fr/api/1/datasets/r/8b681b69-739c-47eb-a96b-06e8e2d8dc08"
)
FICHIER_CONTOURS = DATA_DIR / "data_brut" / "contours_circonscriptions.geojson"


def gel_contours(forcer=False):
    """
    Télécharge le GeoJSON des contours et le sauvegarde dans data_brut.
    Un fichier déjà présent n'est pas retéléchargé, sauf si forcer=True.
    """
    FICHIER_CONTOURS.parent.mkdir(parents=True, exist_ok=True)
    if FICHIER_CONTOURS.exists() and not forcer:
        print("contours_circonscriptions.geojson déjà présent : pas de téléchargement.")
        return
    reponse = requests.get(URL_CONTOURS, headers=HEADERS, timeout=120)
    reponse.raise_for_status()
    FICHIER_CONTOURS.write_bytes(reponse.content)
    print("Contours téléchargés et gelés dans data_brut.")


def charger_contours():
    """Charge les contours en GeoDataFrame."""
    return gpd.read_file(FICHIER_CONTOURS)