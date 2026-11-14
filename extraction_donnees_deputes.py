"""Ingestion, typage, nettoyage de base et audit des sources brutes.

Sources ingérées
----------------
1. INSEE - Portraits des circonscriptions législatives : les liens de
   téléchargement sont découverts en parsant la page HTML, puis les fichiers
   sont téléchargés dans ``data/raw/`` (décompression des ``.zip`` incluse).
2. data.gouv.fr - Députés actifs de l'Assemblée nationale : la ressource CSV
   la plus récente est retrouvée via l'API REST de data.gouv.fr.

Ce module ne réalise **aucune jointure** entre les députés et l'INSEE : il
produit des tables typées dans ``data/interim/`` et un rapport d'audit
(dans les logs) qui prépare la future normalisation des clés géographiques.

Utilisation en ligne de commande, depuis la racine du dépôt::

    python -m src.ingestion            # ou : python src/ingestion.py
    python -m src.ingestion --force    # re-télécharge les fichiers bruts
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constantes (chemins relatifs à la racine du dépôt, aucun chemin local)
# --------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[1]
DATA_RAW = RACINE / "data" / "raw"
DATA_INTERIM = RACINE / "data" / "interim"

URL_INSEE_PAGE = "https://www.insee.fr/fr/statistiques/6436476"
CHEMIN_FICHIERS_INSEE = "/fr/statistiques/fichier/6436476/"
URLS_INSEE_SECOURS = (
    "https://www.insee.fr/fr/statistiques/fichier/6436476/"
    "indic-stat-circonscriptions-legislatives-2022.xlsx",
    "https://www.insee.fr/fr/statistiques/fichier/6436476/circo_composition.xlsx",
)
URL_API_DEPUTES = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "deputes-actifs-de-lassemblee-nationale-informations-et-statistiques/"
)
NOM_FICHIER_DEPUTES = "deputes_actifs.csv"

EXTENSIONS_DONNEES = (".csv", ".zip", ".xlsx")
TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (projet etudiant Python pour la data science)"
ENCODAGES = ("utf-8-sig", "utf-8", "latin-1")
NB_CIRCONSCRIPTIONS = 577

# Marqueurs INSEE de secret statistique ou de valeur non disponible
MARQUEURS_SECRET = frozenset({"s", "nd", "n.d.", "n.d", "nc", "ns", "n.s.", "-"})

# Colonnes à ne jamais convertir en nombres (identifiants, codes, libellés)
REGEX_IDENTIFIANT = re.compile(
    r"code|^cod|_cod|circ|d[ée]partement|^dep($|[\W_])|commune|^com$"
    r"|^id$|_id$|^id_|insee|num[ée]ro",
    re.IGNORECASE,
)
REGEX_FEUILLE_DOC = re.compile(
    r"doc|lisez|notice|sommaire|m[ée]tadon|lexique|dictionnaire", re.IGNORECASE
)
COLONNES_DATES_DEPUTES = ("naissance", "datePriseFonction", "dateMaj")

# Variables clés dont on mesure la complétude
VARIABLES_CLES = {
    "age/naissance": r"(^|[^a-z])(âge|age)([^a-z]|$)|naissance",
    "genre": r"^civ|genre|sexe|femme",
    "profession/PCS": r"job|profession|pcs|csp",
    "circonscription": r"circ",
}


# --------------------------------------------------------------------------
# Réseau : session HTTP, découverte et téléchargement des fichiers
# --------------------------------------------------------------------------
def creer_session() -> requests.Session:
    """Crée une session HTTP avec User-Agent et nouvelles tentatives.

    Returns:
        Session ``requests`` réessayant 3 fois en cas d'erreur 429 ou 5xx.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)
    )
    adaptateur = HTTPAdapter(max_retries=retry)
    session.mount("https://", adaptateur)
    session.mount("http://", adaptateur)
    return session


def extraire_liens_fichiers(
    html: str,
    url_page: str,
    chemin_cible: str = CHEMIN_FICHIERS_INSEE,
    extensions: Sequence[str] = EXTENSIONS_DONNEES,
) -> list[str]:
    """Extrait les liens de fichiers de données d'une page HTML.

    Args:
        html: Contenu HTML de la page.
        url_page: URL de la page, pour résoudre les liens relatifs.
        chemin_cible: Fragment de chemin que doit contenir le lien.
        extensions: Extensions de fichiers retenues.

    Returns:
        Liste d'URL absolues, sans doublon, dans l'ordre de la page.
    """
    soupe = BeautifulSoup(html, "html.parser")
    liens: list[str] = []
    for ancre in soupe.find_all("a", href=True):
        url = urljoin(url_page, str(ancre["href"])).split("#")[0]
        chemin = urlparse(url).path
        correspond = chemin_cible in chemin
        if correspond and chemin.lower().endswith(tuple(extensions)):
            if url not in liens:
                liens.append(url)
    return liens


def decouvrir_urls_insee(session: requests.Session) -> list[str]:
    """Découvre les liens de téléchargement sur la page INSEE.

    Si la page est inaccessible ou ne contient aucun lien exploitable, on
    se rabat sur les URL directes connues (``URLS_INSEE_SECOURS``).

    Args:
        session: Session HTTP.

    Returns:
        Liste d'URL de fichiers à télécharger.
    """
    try:
        reponse = session.get(URL_INSEE_PAGE, timeout=TIMEOUT)
        reponse.raise_for_status()
        liens = extraire_liens_fichiers(reponse.text, URL_INSEE_PAGE)
    except requests.RequestException as erreur:
        logger.warning("Page INSEE inaccessible (%s) : URL de secours.", erreur)
        return list(URLS_INSEE_SECOURS)
    if not liens:
        logger.warning("Aucun lien de fichier trouvé : URL de secours.")
        return list(URLS_INSEE_SECOURS)
    if not any(lien.lower().endswith((".csv", ".zip")) for lien in liens):
        logger.warning(
            "Aucun .csv/.zip publié : la page propose des fichiers %s.",
            sorted({Path(urlparse(u).path).suffix for u in liens}),
        )
    logger.info("%d fichier(s) découvert(s) sur la page INSEE.", len(liens))
    return liens


def telecharger_fichier(
    session: requests.Session, url: str, dossier: Path, force: bool = False
) -> Path:
    """Télécharge un fichier dans ``dossier`` s'il n'est pas déjà en cache.

    Args:
        session: Session HTTP.
        url: URL du fichier.
        dossier: Dossier de destination (créé si besoin).
        force: Si vrai, re-télécharge même si le fichier existe.

    Returns:
        Chemin du fichier local.

    Raises:
        requests.HTTPError: Si le serveur renvoie une erreur HTTP.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / Path(urlparse(url).path).name
    if destination.exists() and not force:
        logger.info("Cache local utilisé : %s", destination.name)
        return destination
    logger.info("Téléchargement : %s", url)
    reponse = session.get(url, timeout=TIMEOUT)
    reponse.raise_for_status()
    destination.write_bytes(reponse.content)
    logger.info("  -> %s (%d Ko)", destination.name, len(reponse.content) // 1024)
    return destination


def decompresser_zip(chemin_zip: Path, dossier: Path) -> list[Path]:
    """Extrait les fichiers de données (.csv, .xlsx) d'une archive zip.

    Seuls les noms de fichiers sont conservés (pas d'arborescence), ce qui
    évite les écritures hors du dossier cible.

    Args:
        chemin_zip: Archive à ouvrir.
        dossier: Dossier d'extraction.

    Returns:
        Chemins des fichiers extraits.
    """
    extraits: list[Path] = []
    with zipfile.ZipFile(chemin_zip) as archive:
        for membre in archive.namelist():
            nom = Path(membre).name
            valide = nom.lower().endswith((".csv", ".xlsx"))
            if not nom or not valide or "__MACOSX" in membre:
                continue
            destination = dossier / nom
            if not destination.exists():
                destination.write_bytes(archive.read(membre))
            extraits.append(destination)
    logger.info("Archive %s : %d fichier(s) de données.", chemin_zip.name, len(extraits))
    return extraits


def lister_fichiers_donnees(chemins: Iterable[Path], dossier: Path) -> list[Path]:
    """Remplace chaque archive zip par les fichiers qu'elle contient.

    Args:
        chemins: Fichiers téléchargés (csv, xlsx ou zip).
        dossier: Dossier où extraire les archives.

    Returns:
        Liste de fichiers .csv ou .xlsx prêts à être lus.
    """
    fichiers: list[Path] = []
    for chemin in chemins:
        if chemin.suffix.lower() == ".zip":
            fichiers.extend(decompresser_zip(chemin, dossier))
        else:
            fichiers.append(chemin)
    return fichiers


# --------------------------------------------------------------------------
# Lecture typée des fichiers (tout en texte, conversion explicite ensuite)
# --------------------------------------------------------------------------
def detecter_separateur(echantillon: str) -> str:
    """Détecte le séparateur d'un CSV (``;``, ``,``, tabulation ou ``|``).

    Args:
        echantillon: Début du fichier, décodé.

    Returns:
        Le caractère séparateur.
    """
    try:
        return csv.Sniffer().sniff(echantillon, delimiters=";,\t|").delimiter
    except csv.Error:
        return ";" if echantillon.count(";") >= echantillon.count(",") else ","


def lire_csv(chemin: Path) -> pd.DataFrame:
    """Lit un CSV en texte (``dtype=str``) avec détection d'encodage et de séparateur.

    Args:
        chemin: Fichier CSV.

    Returns:
        DataFrame dont toutes les colonnes sont des chaînes (``NaN`` si vide).
    """
    brut = chemin.read_bytes()
    texte = ""
    encodage = ENCODAGES[-1]
    for encodage in ENCODAGES:
        try:
            texte = brut.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    separateur = detecter_separateur(texte[:5000])
    logger.info("%s : encodage=%s, séparateur=%r", chemin.name, encodage, separateur)
    return pd.read_csv(
        io.StringIO(texte),
        sep=separateur,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
    )


def detecter_entete(brut: pd.DataFrame, essais: int = 20) -> int:
    """Repère la ligne de titres : la première ligne la plus riche en texte.

    Args:
        brut: Feuille lue sans en-tête (``header=None``).
        essais: Nombre de premières lignes examinées.

    Returns:
        Indice (à partir de 0) de la ligne d'en-tête.
    """
    scores = [
        (int(brut.iloc[i].map(lambda v: isinstance(v, str)).sum()), -i)
        for i in range(min(essais, len(brut)))
    ]
    return -max(scores)[1] if scores else 0


def choisir_feuille(classeur: pd.ExcelFile) -> str:
    """Choisit la feuille de données : la plus longue hors documentation.

    Args:
        classeur: Fichier Excel ouvert.

    Returns:
        Nom de la feuille retenue.
    """
    noms = [n for n in classeur.sheet_names if not REGEX_FEUILLE_DOC.search(n)]
    noms = noms or list(classeur.sheet_names)
    return max(noms, key=lambda n: classeur.parse(n, header=None).shape[0])


def lire_excel(
    chemin: Path, feuille: str | None = None, entete: int | None = None
) -> pd.DataFrame:
    """Lit une feuille Excel en texte (``dtype=str``), titres détectés si besoin.

    Args:
        chemin: Fichier .xlsx.
        feuille: Nom de la feuille (détection automatique si ``None``).
        entete: Ligne des titres (détection automatique si ``None``).

    Returns:
        DataFrame dont toutes les colonnes sont des chaînes.
    """
    classeur = pd.ExcelFile(chemin, engine="openpyxl")
    feuille = feuille or choisir_feuille(classeur)
    brut = classeur.parse(feuille, header=None)
    entete = detecter_entete(brut) if entete is None else entete
    logger.info("%s : feuille « %s », titres en ligne %d", chemin.name, feuille, entete)
    return classeur.parse(feuille, header=entete, dtype=str)


def charger_table(chemin: Path) -> pd.DataFrame:
    """Charge un fichier .csv ou .xlsx en DataFrame de texte.

    Args:
        chemin: Fichier à lire.

    Returns:
        DataFrame brut (toutes colonnes en chaînes).

    Raises:
        ValueError: Si l'extension n'est pas prise en charge.
    """
    suffixe = chemin.suffix.lower()
    if suffixe == ".csv":
        return lire_csv(chemin)
    if suffixe == ".xlsx":
        return lire_excel(chemin)
    raise ValueError(f"Extension non prise en charge : {chemin.name}")


# --------------------------------------------------------------------------
# Nettoyage de base et typage
# --------------------------------------------------------------------------
def nettoyer_base(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage de base : titres, espaces, vides et lignes/colonnes vides.

    Args:
        df: Table brute (colonnes en texte).

    Returns:
        Nouvelle table nettoyée (la table d'entrée n'est pas modifiée).
    """
    propre = df.copy()
    propre.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in propre.columns]
    for colonne in propre.columns:
        if pd.api.types.is_object_dtype(propre[colonne]) or pd.api.types.is_string_dtype(
            propre[colonne]
        ):
            serie = propre[colonne].astype("string").str.strip()
            propre[colonne] = serie.mask(serie == "").astype(object)
    propre = propre.dropna(how="all").dropna(axis=1, how="all")
    return propre.reset_index(drop=True)


def nettoyer_nombres(serie: pd.Series) -> pd.Series:
    """Prépare des nombres à la française pour la conversion.

    Retire espaces (y compris insécables), remplace la virgule décimale et
    transforme les marqueurs de secret statistique INSEE en valeurs manquantes.

    Args:
        serie: Série de chaînes.

    Returns:
        Série de chaînes prêtes pour ``pd.to_numeric``.
    """
    texte = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"[\s\u00a0\u202f]", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    return texte.mask(texte.str.lower().isin(MARQUEURS_SECRET))


def convertir_serie_numerique(serie: pd.Series) -> pd.Series:
    """Convertit une série de chaînes en ``float64`` (erreurs -> ``NaN``).

    Args:
        serie: Série de chaînes (virgules françaises, secret INSEE).

    Returns:
        Série de nombres décimaux.
    """
    convertie = pd.to_numeric(nettoyer_nombres(serie), errors="coerce")
    return convertie.astype("float64")


def convertir_numeriques(
    df: pd.DataFrame, seuil: float = 0.9
) -> tuple[pd.DataFrame, list[str]]:
    """Convertit en nombres les colonnes qui en contiennent, hors identifiants.

    Une colonne est convertie si au moins ``seuil`` de ses valeurs non vides
    (hors marqueurs de secret) sont lisibles comme des nombres. Les colonnes
    dont le nom ressemble à un code (département, circonscription, commune,
    identifiant...) restent en texte pour préserver les zéros initiaux.

    Args:
        df: Table nettoyée (colonnes en texte).
        seuil: Part minimale de valeurs numériques pour convertir.

    Returns:
        Tuple (table typée, liste des colonnes converties).
    """
    resultat = df.copy()
    converties: list[str] = []
    for colonne in resultat.columns:
        if REGEX_IDENTIFIANT.search(colonne):
            continue
        valides = nettoyer_nombres(resultat[colonne]).dropna()
        if valides.empty:
            continue
        nombres = pd.to_numeric(valides, errors="coerce")
        if nombres.notna().mean() >= seuil:
            resultat[colonne] = convertir_serie_numerique(resultat[colonne])
            converties.append(colonne)
    return resultat, converties


def convertir_dates(
    df: pd.DataFrame, colonnes: Iterable[str]
) -> tuple[pd.DataFrame, list[str]]:
    """Convertit les colonnes indiquées en dates (``NaT`` si illisible).

    Args:
        df: Table à typer.
        colonnes: Noms de colonnes de dates, ignorés s'ils sont absents.

    Returns:
        Tuple (table typée, liste des colonnes converties).
    """
    resultat = df.copy()
    converties: list[str] = []
    for colonne in colonnes:
        if colonne not in resultat.columns:
            continue
        resultat[colonne] = pd.to_datetime(resultat[colonne], errors="coerce")
        converties.append(colonne)
    return resultat, converties


def preparer_table(
    df: pd.DataFrame, colonnes_dates: Iterable[str] = ()
) -> pd.DataFrame:
    """Enchaîne nettoyage de base, typage numérique et typage des dates.

    Args:
        df: Table brute.
        colonnes_dates: Colonnes à convertir en dates.

    Returns:
        Table typée.
    """
    propre = nettoyer_base(df)
    typee, numeriques = convertir_numeriques(propre)
    typee, dates = convertir_dates(typee, colonnes_dates)
    logger.info("Colonnes numériques : %s", numeriques or "aucune")
    logger.info("Colonnes de dates : %s", dates or "aucune")
    return typee


# --------------------------------------------------------------------------
# Audit pré-jointure
# --------------------------------------------------------------------------
def trouver_colonne(
    colonnes: Sequence[str], motifs: Sequence[str], exclure: Sequence[str] = ()
) -> str | None:
    """Trouve la première colonne dont le nom contient tous les motifs.

    Args:
        colonnes: Noms de colonnes.
        motifs: Expressions régulières à toutes vérifier (insensible à la casse).
        exclure: Expressions régulières qui écartent une colonne.

    Returns:
        Nom de la colonne, ou ``None``.
    """
    for colonne in colonnes:
        bas = colonne.lower()
        if all(re.search(m, bas) for m in motifs) and not any(
            re.search(e, bas) for e in exclure
        ):
            return colonne
    return None


def classer_zone(code: object) -> str:
    """Classe un code département ou circonscription par grande zone.

    Args:
        code: Code (``'01'``, ``'2B'``, ``'971'``, ``'099'``, ``'9201'``...).

    Returns:
        ``'metropole'``, ``'corse'``, ``'drom_com'``, ``'hors_france'`` ou
        ``'autre'``.
    """
    texte = str(code).strip().upper()
    if len(texte) == 3 and texte.isdigit() and texte.startswith("0"):
        texte = texte[1:]  # '099' (Français de l'étranger dans Datan) -> '99'
    if texte.startswith(("2A", "2B")):
        return "corse"
    if texte.startswith(("ZZ", "99")):
        return "hors_france"
    if texte.startswith(("97", "98")):
        return "drom_com"
    if texte[:2].isdigit() and 1 <= int(texte[:2]) <= 95:
        return "metropole"
    return "autre"


def auditer_table(
    df: pd.DataFrame,
    nom: str,
    unite: str,
    cles_candidates: Sequence[Sequence[str]] | None = None,
    attendu_circos: int | None = None,
) -> dict[str, Any]:
    """Journalise l'audit d'une table : grain, clés géographiques, complétude.

    Args:
        df: Table typée à auditer.
        nom: Nom de la table (pour les logs).
        unite: Unité statistique attendue (une ligne = ...).
        cles_candidates: Clés candidates à tester (listes de colonnes). Si
            ``None``, elles sont déduites des colonnes de circonscription.
        attendu_circos: Nombre de circonscriptions attendu, s'il y a lieu.

    Returns:
        Dictionnaire de synthèse (dimensions, unicité des clés, nombre de
        circonscriptions, taux de valeurs manquantes) utile pour les tests.
    """
    colonnes = list(df.columns)
    col_dep = trouver_colonne(colonnes, [r"d[ée]p", r"cod"]) or trouver_colonne(
        colonnes, [r"d[ée]p"], exclure=[r"nom", r"lib"]
    )
    col_circo = trouver_colonne(colonnes, [r"circ"], exclure=[r"nom", r"lib"])
    synthese: dict[str, Any] = {"nom": nom, "lignes": len(df), "colonnes": df.shape[1]}

    logger.info("===== AUDIT : %s =====", nom)
    logger.info("1. Dimensions : %d lignes x %d colonnes", *df.shape)
    logger.info("   Grain statistique attendu : une ligne = %s", unite)

    if cles_candidates is None:
        identifiant = trouver_colonne(colonnes, [r"^id$"])
        cles_candidates = [[identifiant]] if identifiant else []
        if col_circo:
            cles_candidates = [*cles_candidates, [c for c in (col_dep, col_circo) if c]]
    unicite: dict[str, bool] = {}
    for cle in cles_candidates:
        if not set(cle) <= set(colonnes):
            logger.warning("   Clé %s absente de la table.", list(cle))
            continue
        distincts = len(df[list(cle)].dropna().drop_duplicates())
        unicite["+".join(cle)] = distincts == len(df)
        logger.info(
            "   Clé %s : %d valeurs distinctes pour %d lignes -> %s",
            list(cle),
            distincts,
            len(df),
            "UNIQUE" if distincts == len(df) else "NON unique",
        )
    synthese["cles_uniques"] = unicite

    colonnes_geo = [c for c in colonnes if re.search(r"circ|d[ée]p|commune|code", c, re.I)]
    logger.info("2. Colonnes géographiques détectées : %s", colonnes_geo or "aucune")
    col_zone = col_dep or col_circo
    for colonne in (c for c in (col_dep, col_circo) if c):
        valeurs = df[colonne].dropna().astype(str)
        logger.info(
            "   %s (dtype=%s) : %d valeurs distinctes, exemples %s",
            colonne,
            df[colonne].dtype,
            valeurs.nunique(),
            valeurs.unique()[:5].tolist(),
        )
    if col_zone:
        par_zone: dict[str, list[str]] = {}
        for valeur in df[col_zone].dropna().astype(str).unique():
            par_zone.setdefault(classer_zone(valeur), []).append(valeur)
        exemples = {zone: vals[:3] for zone, vals in sorted(par_zone.items())}
        logger.info("   Exemples par zone (%s) : %s", col_zone, exemples)
        synthese["zones"] = sorted(par_zone)

    nb_circos = None
    if col_circo:
        nb_circos = len(df[[c for c in (col_dep, col_circo) if c]].dropna().drop_duplicates())
        logger.info("   Circonscriptions uniques : %d", nb_circos)
        if attendu_circos is not None and nb_circos != attendu_circos:
            logger.warning(
                "   Écart avec les %d circonscriptions attendues (sièges vacants, "
                "codes à normaliser ou table partielle).",
                attendu_circos,
            )
    synthese["nb_circonscriptions"] = nb_circos

    manquants: dict[str, float] = {}
    for libelle, motif in VARIABLES_CLES.items():
        for colonne in [c for c in colonnes if re.search(motif, c.lower())][:10]:
            manquants[f"{libelle} | {colonne}"] = round(100 * df[colonne].isna().mean(), 1)
    logger.info("3. Valeurs manquantes (%%) sur les variables clés :")
    if manquants:
        logger.info("\n%s", pd.Series(manquants, name="% manquant").to_string())
    else:
        logger.info("   Aucune variable clé détectée par son nom.")
    synthese["manquants"] = manquants
    return synthese


# --------------------------------------------------------------------------
# Sorties et orchestration
# --------------------------------------------------------------------------
def exporter_table(df: pd.DataFrame, nom: str, dossier: Path = DATA_INTERIM) -> Path:
    """Exporte une table en Parquet (CSV UTF-8 si ``pyarrow`` est absent).

    Args:
        df: Table à écrire.
        nom: Nom du fichier sans extension.
        dossier: Dossier de sortie (créé si besoin).

    Returns:
        Chemin du fichier écrit.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    try:
        chemin = dossier / f"{nom}.parquet"
        df.to_parquet(chemin, index=False)
    except ImportError:
        logger.warning("pyarrow absent : export en CSV UTF-8.")
        chemin = dossier / f"{nom}.csv"
        df.to_csv(chemin, index=False, encoding="utf-8")
    logger.info("Table écrite : %s", chemin.relative_to(RACINE) if chemin.is_relative_to(RACINE) else chemin)
    return chemin


def classer_tables_insee(tables: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Distingue indicateurs, métadonnées et composition sans rien écraser.

    Règles : présence de ``COD_VAR``/``LIB_VAR`` -> métadonnées ; nom de
    fichier contenant « compo » -> composition (communes/circonscriptions) ;
    sinon -> indicateurs. En cas de rôle déjà pris, un suffixe numérique est
    ajouté plutôt que d'écraser la table précédente.

    Args:
        tables: Tables chargées, indexées par nom de fichier (sans extension).

    Returns:
        Tables indexées par rôle (``indicateurs``, ``metadonnees``...).
    """
    roles: dict[str, pd.DataFrame] = {}
    for nom, df in tables.items():
        colonnes = {str(c).upper() for c in df.columns}
        if colonnes & {"COD_VAR", "LIB_VAR"}:
            base = "metadonnees"
        elif "compo" in nom.lower():
            base = "composition"
        else:
            base = "indicateurs"
        role, i = base, 2
        while role in roles:
            role, i = f"{base}_{i}", i + 1
        roles[role] = df
        logger.info("Fichier %s classé comme « %s ».", nom, role)
    return roles


def ingerer_insee(
    session: requests.Session,
    dossier_raw: Path = DATA_RAW,
    dossier_interim: Path = DATA_INTERIM,
    force: bool = False,
) -> dict[str, pd.DataFrame]:
    """Télécharge, type, exporte et audite les fichiers INSEE.

    Args:
        session: Session HTTP.
        dossier_raw: Dossier des fichiers bruts.
        dossier_interim: Dossier des tables nettoyées.
        force: Re-télécharger même si le cache existe.

    Returns:
        Tables typées indexées par rôle.
    """
    urls = decouvrir_urls_insee(session)
    telecharges = [telecharger_fichier(session, u, dossier_raw, force) for u in urls]
    fichiers = lister_fichiers_donnees(telecharges, dossier_raw)
    brutes = {f.stem: charger_table(f) for f in fichiers}
    resultat: dict[str, pd.DataFrame] = {}
    for role, df in classer_tables_insee(brutes).items():
        table = preparer_table(df)
        resultat[role] = table
        exporter_table(table, f"insee_{role}", dossier_interim)
        if role.startswith("indicateurs"):
            auditer_table(
                table, f"INSEE {role}", "circonscription législative",
                attendu_circos=NB_CIRCONSCRIPTIONS,
            )
        elif role.startswith("composition"):
            auditer_table(table, f"INSEE {role}", "couple commune x circonscription")
        else:
            auditer_table(table, f"INSEE {role}", "variable (dictionnaire)")
    return resultat


def choisir_ressource_csv(ressources: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Choisit la ressource CSV la plus récente d'un jeu data.gouv.fr.

    Args:
        ressources: Champ ``resources`` de la réponse de l'API.

    Returns:
        La ressource CSV dont la date de dernière modification est la plus récente.

    Raises:
        ValueError: S'il n'y a aucune ressource CSV.
    """
    csvs = [
        r for r in ressources
        if str(r.get("format", "")).lower() == "csv"
        or str(r.get("url", "")).lower().split("?")[0].endswith(".csv")
    ]
    if not csvs:
        raise ValueError("Aucune ressource CSV dans le jeu de données.")
    return max(csvs, key=lambda r: str(r.get("last_modified") or r.get("created_at") or ""))


def ingerer_deputes(
    session: requests.Session,
    dossier_raw: Path = DATA_RAW,
    dossier_interim: Path = DATA_INTERIM,
    force: bool = False,
) -> pd.DataFrame:
    """Télécharge (via l'API data.gouv.fr), type, exporte et audite les députés.

    Le jeu étant mis à jour quotidiennement, une copie en cache peut être
    périmée : utiliser ``force=True`` pour la rafraîchir.

    Args:
        session: Session HTTP.
        dossier_raw: Dossier des fichiers bruts.
        dossier_interim: Dossier des tables nettoyées.
        force: Re-télécharger même si le cache existe.

    Returns:
        Table typée des députés actifs.
    """
    destination = dossier_raw / NOM_FICHIER_DEPUTES
    if force or not destination.exists():
        reponse = session.get(URL_API_DEPUTES, timeout=TIMEOUT)
        reponse.raise_for_status()
        ressource = choisir_ressource_csv(reponse.json().get("resources", []))
        logger.info("Ressource retenue : %s", ressource.get("url"))
        dossier_raw.mkdir(parents=True, exist_ok=True)
        fichier = session.get(str(ressource["url"]), timeout=TIMEOUT)
        fichier.raise_for_status()
        destination.write_bytes(fichier.content)
    else:
        logger.info("Cache local utilisé : %s", destination.name)
    table = preparer_table(lire_csv(destination), COLONNES_DATES_DEPUTES)
    exporter_table(table, "deputes_actifs", dossier_interim)
    auditer_table(
        table, "Députés actifs", "député",
        cles_candidates=None, attendu_circos=NB_CIRCONSCRIPTIONS,
    )
    return table


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée : ingère et audite les 3 sources.

    Args:
        argv: Arguments de ligne de commande (``None`` = ``sys.argv``).

    Returns:
        Code de sortie (0 si succès, 1 en cas d'erreur).
    """
    parseur = argparse.ArgumentParser(description="Ingestion des sources brutes.")
    parseur.add_argument("--force", action="store_true", help="re-télécharger")
    parseur.add_argument("--log-level", default="INFO", help="niveau de log")
    args = parseur.parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    session = creer_session()
    try:
        ingerer_insee(session, force=args.force)
        ingerer_deputes(session, force=args.force)
    except (requests.RequestException, OSError, ValueError) as erreur:
        logger.error("Échec de l'ingestion : %s", erreur)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())