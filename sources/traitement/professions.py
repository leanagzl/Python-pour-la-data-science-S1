"""
Recodage de la profession déclarée des députés (colonne 'job') en grandes
catégories socioprofessionnelles, comparables aux variables 'act_*' de l'INSEE.
"""

import re
import unicodedata

# Premier chiffre du code PCS -> catégorie (variables INSEE act_agr, act_art...)
PCS_PREMIER_CHIFFRE = {
    "1": "agr", "2": "art", "3": "cad", "4": "int", "5": "emp", "6": "ouv",
}
# Anciens actifs (codes 7x) rattachés à leur ancienne catégorie
PCS_ANCIENS = {
    "71": "agr", "72": "art", "74": "cad", "75": "int", "77": "emp", "78": "ouv",
}

# Règles par mots-clés (texte sans accents ni majuscules, tirets remplacés
# par des espaces), dans l'ordre : la première règle qui correspond l'emporte.
# Les libellés ambigus (« enseignant », « fonctionnaire territorial »...)
# restent volontairement non classés.
REGLES = [
    ("inactif", ["sans profession", "sans activite", "eleve, etudiant",
                 "etudiant"]),
    ("politique", ["collaborat", "permanent politique", "directeur de cabinet",
                   "directrice de cabinet", "chef de cabinet", "parlementaire",
                   "ministre", "ministerielle"]),
    ("agr", ["agricult", "exploitant agricole", "viticult", "eleveur"]),
    ("art", ["artisan", "commercant", "chef d'entreprise",
             "cheffe d'entreprise", "industriel", "entrepreneur", "dirigeant",
             "menuisier"]),
    ("int", ["profession intermediaire", "professeur des ecoles",
             "professeur d'ecole", "instituteur", "1er deg",
             "fonctionnaire de categorie b", "educateur", "educatrice",
             "infirmier", "representant de commerce", "technicien",
             "directrice d'ecole", "directeur d'ecole",
             "preparatrice en pharmacie", "intervenant social",
             "insertion professionnelle"]),
    ("emp", ["employ", "policier", "agent de service", "clerc d'huissier",
             "assistante familiale", "police nationale", "militaire"]),
    ("ouv", ["ouvrier", "electricien", "chauffeur", "siderurgie"]),
    ("cad", ["cadre", "ingenieur", "avocat", "profession liberale",
             "pharmacien", "medecin", "notaire", "juriste", "magistrat",
             "professeur", "maitre de conferences", "enseignement superieur",
             "journaliste", "profession de l'information", "directeur",
             "directrice", "consultant", "expert comptable", "psychologue",
             "inspecteur general", "conseiller referendaire", "biologiste",
             "fonctionnaire de categorie a", "chef de projet", "chirurgien",
             "cardiolog", "kinesitherapeute", "osteopathe", "sociologue",
             "historien", "maitre des requetes", "inspecteur principal",
             "inspecteur des finances", "analyste bancaire", "risk manager",
             "delegue general", "artiste", "attachee de presse",
             "photographe", "reporter", "responsable d'usine",
             "responsable de la communication", "officier"]),
    # En dernier : un retraité dont l'ancien métier n'a pas été reconnu
    ("inactif", ["retraite"]),
]


def _normaliser(texte):
    """Minuscules, sans accents, tirets et apostrophes typographiques unifiés."""
    texte = texte.lower().replace("-", " ").replace("’", "'")
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def recoder_profession(job):
    """
    Renvoie la catégorie d'une profession : 'agr', 'art', 'cad', 'int', 'emp',
    'ouv', 'politique', 'inactif' ou 'non_classe'.
    """
    job = job.strip()
    code = re.match(r"^\((\d{2})\)", job)
    if code:
        c = code.group(1)
        if c[0] in PCS_PREMIER_CHIFFRE:
            return PCS_PREMIER_CHIFFRE[c[0]]
        if c[0] == "8":
            return "inactif"
        return PCS_ANCIENS.get(c, "non_classe")

    texte = _normaliser(job)
    for categorie, mots in REGLES:
        if any(mot in texte for mot in mots):
            return categorie
    return "non_classe"


def ajouter_categorie_job(df):
    df = df.copy()
    df["csp_depute"] = df["job"].apply(recoder_profession)
    return df