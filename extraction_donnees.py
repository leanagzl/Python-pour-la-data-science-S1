"""
Module de récupération et de nettoyage des données (Députés et INSEE).
"""

from pathlib import Path
import requests
import pandas as pd

# Chemins et URLs des sources
DATA_DIR = Path(__file__).resolve().parent / "data"

URL_INSEE_INDIC = (
    "https://www.insee.fr/fr/statistiques/fichier/6436476/"
    "indic-stat-circonscriptions-legislatives-2022.xlsx"
)
URL_INSEE_COMPO = (
    "https://www.insee.fr/fr/statistiques/fichier/6436476/circo_composition.xlsx"
)
URL_API_DEPUTES = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "deputes-actifs-de-lassemblee-nationale-informations-et-statistiques/"
)
HEADERS = {"User-Agent": "Python data science project"}


# Téléchargement et sauvegarde des fichiers bruts de l'INSEE


def gel_donnees_insee(forcer=False):
    """
    Télécharge les deux fichiers Excel de l'INSEE et les sauvegarde dans data_brut.
    Un fichier déjà présent n'est pas retéléchargé, sauf si forcer=True.
    """
    dossier_brut = DATA_DIR / "data_brut"
    dossier_brut.mkdir(parents=True, exist_ok=True)

    fichiers = {
        "indic-stat-circonscriptions-legislatives-2022.xlsx": URL_INSEE_INDIC,
        "circo_composition.xlsx": URL_INSEE_COMPO,
    }

    for nom_fichier, url in fichiers.items():
        output_path = dossier_brut / nom_fichier
        if output_path.exists() and not forcer:
            print(f"{nom_fichier} déjà présent dans data_brut : pas de téléchargement.")
            continue
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        print(f"{nom_fichier} téléchargé et gelé dans data_brut.")
    print("Les fichiers INSEE ont été téléchargés et gelés dans data_brut.")


# Téléchargement et sauvegarde de la base brute des députés


def gel_donnees_deputes(nom_fichier="deputes_actifs.csv", forcer=False):
    """
    Récupère via l'API data.gouv.fr le CSV le plus récent des députés actifs
    et le sauvegarde dans data_brut. Un fichier déjà présent n'est pas
    retéléchargé (la liste change chaque jour), sauf si forcer=True.

    Paramètres
    ----------
    nom_fichier : str, optionnel
        Nom du fichier CSV de sortie.
    forcer : bool, optionnel
        Si True, retélécharge même si le fichier existe.
    """
    dossier_brut = DATA_DIR / "data_brut"
    dossier_brut.mkdir(parents=True, exist_ok=True)
    output_path = dossier_brut / nom_fichier

    if output_path.exists() and not forcer:
        print(f"{nom_fichier} déjà présent dans data_brut : pas de téléchargement.")
        return

    response = requests.get(URL_API_DEPUTES, headers=HEADERS, timeout=30)
    response.raise_for_status()
    ressources = response.json()["resources"]

    # Sélection de la ressource CSV la plus récente
    csv_ressources = [r for r in ressources if r.get("format", "").lower() == "csv"]
    derniere_csv = max(csv_ressources, key=lambda r: r.get("last_modified", ""))

    resp_csv = requests.get(derniere_csv["url"], headers=HEADERS, timeout=60)
    resp_csv.raise_for_status()

    output_path.write_bytes(resp_csv.content)
    print("La base des députés a été téléchargée et gelée dans data_brut.")


# Lecture d'un fichier Excel INSEE


def lire_excel_insee(chemin_fichier, onglet_donnees, ligne_entete, onglet_doc):
    """
    Lit l'onglet de données et l'onglet de documentation d'un fichier Excel INSEE.

    Paramètres
    ----------
    chemin_fichier : Path
        Chemin vers le fichier Excel INSEE.
    onglet_donnees : int
        Indice de l'onglet contenant les données.
    ligne_entete : int
        Indice de la ligne contenant les noms de colonnes dans cet onglet.
    onglet_doc : int
        Indice de l'onglet contenant la documentation (dictionnaire des variables).

    Retour
    ------
    df_donnees : pandas.DataFrame
        Tableau principal des données (colonnes lues en texte).
    df_doc : pandas.DataFrame
        Onglet de documentation.
    """
    df_doc = pd.read_excel(
        chemin_fichier, sheet_name=onglet_doc, dtype=str
    ).dropna(how="all")
    df_donnees = pd.read_excel(
        chemin_fichier, sheet_name=onglet_donnees, header=ligne_entete, dtype=str
    )
    return df_donnees, df_doc


# Nettoyage des indicateurs INSEE par circonscription


def nettoyer_insee_indic(df):
    """
    Nettoie la table des indicateurs INSEE : crée la clé 'code_circo' et
    convertit les indicateurs statistiques en numérique.

    Paramètres
    ----------
    df : pandas.DataFrame
        DataFrame brut des indicateurs INSEE.

    Retour
    ------
    df_clean : pandas.DataFrame
        DataFrame nettoyé.
    """
    df_clean = df.dropna(how="all").copy()
    df_clean.columns = df_clean.columns.str.strip()

    # La 1re colonne contient le code de la circonscription ('0101', '2A01', '97101')
    col_code = df_clean.columns[0]
    df_clean["code_circo"] = df_clean[col_code].str.strip().str.upper().str.zfill(5)

    # Conversion des colonnes statistiques en nombres (les 's' et 'nd' deviennent NaN)
    colonnes_texte = {col_code, df_clean.columns[1], "code_circo"}
    for col in df_clean.columns:
        if col in colonnes_texte:
            continue
        serie = df_clean[col].str.replace(",", ".", regex=False).str.strip()
        convertie = pd.to_numeric(serie, errors="coerce")
        if convertie.notna().sum() > len(df_clean) * 0.5:
            df_clean[col] = convertie

    return df_clean


# Nettoyage de la table de composition des circonscriptions


def nettoyer_insee_compo(df):
    """
    Nettoie la table INSEE de correspondance communes - circonscriptions.

    Paramètres
    ----------
    df : pandas.DataFrame
        DataFrame brut de composition des circonscriptions.

    Retour
    ------
    df_clean : pandas.DataFrame
        DataFrame nettoyé.
    """
    df_clean = df.dropna(how="all").copy()
    df_clean.columns = df_clean.columns.str.strip()
    return df_clean


# Nettoyage de la base des députés actifs


def nettoyer_deputes(df):
    """
    Nettoie la base des députés actifs et crée la clé 'code_circo' au format INSEE
    (5 caractères, ex. '75018' ou '97101').

    Paramètres
    ----------
    df : pandas.DataFrame
        DataFrame brut des députés actifs.

    Retour
    ------
    df_clean : pandas.DataFrame
        DataFrame nettoyé.
    """
    df_clean = df.copy()
    df_clean.columns = df_clean.columns.str.strip()

    # Datan écrit les départements sur 3 chiffres ('001'), l'INSEE sur 2 ('01')
    dep = df_clean["departementCode"].str.strip()
    dep = dep.apply(lambda x: x[1:] if len(x) == 3 and x.startswith("0") else x)
    circ = df_clean["circo"].str.strip()

    # Format INSEE sur 5 caractères : département (2) + circo (3) en métropole,
    # département (3) + circo (2) en outre-mer ('971' + '01')
    df_clean["code_circo"] = [
        d + c.zfill(2 if len(d) == 3 else 3) for d, c in zip(dep, circ)
    ]

    # Corse : l'INSEE écrit '2A' et '2B' en majuscules
    df_clean["code_circo"] = df_clean["code_circo"].str.upper()

    # Saint-Barthélemy ('97701') est regroupée avec Saint-Martin ('97801') par l'INSEE
    df_clean["code_circo"] = df_clean["code_circo"].replace({"97701": "97801"})

    if "age" in df_clean.columns:
        df_clean["age"] = pd.to_numeric(df_clean["age"], errors="coerce")

    for col in ["naissance", "datePriseFonction", "dateMaj"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")

    return df_clean

# Construction et sauvegarde des bases nettoyées dans data_clean


def gel_bases_clean():
    """
    Charge les données brutes depuis data_brut, les nettoie séparément
    (sans jointure) et sauvegarde les bases propres dans data_clean.
    """
    dossier_brut = DATA_DIR / "data_brut"
    dossier_clean = DATA_DIR / "data_clean"
    dossier_clean.mkdir(parents=True, exist_ok=True)

       # Lecture des fichiers bruts
    deputes_brut = pd.read_csv(dossier_brut / "deputes_actifs.csv", dtype=str)
    indic_brut, dico_insee = lire_excel_insee(
        dossier_brut / "indic-stat-circonscriptions-legislatives-2022.xlsx",
        onglet_donnees=0,
        ligne_entete=7,
        onglet_doc=1,
    )
    compo_brut, _ = lire_excel_insee(
        dossier_brut / "circo_composition.xlsx",
        onglet_donnees=1,
        ligne_entete=0,
        onglet_doc=0,
    )


    # Nettoyage séparé
    deputes = nettoyer_deputes(deputes_brut)
    insee_indic = nettoyer_insee_indic(indic_brut)
    insee_compo = nettoyer_insee_compo(compo_brut)

    # Sauvegarde dans data_clean
    deputes.to_parquet(dossier_clean / "deputes_clean.parquet", index=False)
    insee_indic.to_parquet(dossier_clean / "insee_indic_clean.parquet", index=False)
    insee_compo.to_parquet(dossier_clean / "insee_compo_clean.parquet", index=False)
    dico_insee.to_csv(dossier_clean / "dictionnaire_insee.csv", index=False)

    print("Les bases nettoyées ont été correctement gelées dans data_clean.")


# Chargement des données propres pour le notebook


def charger_donnees():
    """
    Charge les bases nettoyées depuis data_clean pour l'analyse et les jointures.

    Retour
    ------
    deputes : pandas.DataFrame
        Base nettoyée des députés actifs.
    insee_indic : pandas.DataFrame
        Indicateurs INSEE par circonscription législative.
    insee_compo : pandas.DataFrame
        Table de correspondance communes - circonscriptions.
    dico_insee : pandas.DataFrame
        Dictionnaire des variables INSEE.
    """
    dossier_clean = DATA_DIR / "data_clean"

    deputes = pd.read_parquet(dossier_clean / "deputes_clean.parquet")
    insee_indic = pd.read_parquet(dossier_clean / "insee_indic_clean.parquet")
    insee_compo = pd.read_parquet(dossier_clean / "insee_compo_clean.parquet")
    dico_insee = pd.read_csv(dossier_clean / "dictionnaire_insee.csv", dtype=str)

    return deputes, insee_indic, insee_compo, dico_insee