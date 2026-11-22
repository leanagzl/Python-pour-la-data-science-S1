"""
Comparaison entre le profil des députés et celui de leur circonscription.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import chi2_contingency, kruskal, mannwhitneyu, pearsonr, spearmanr

from descriptif import taux_chomage


def preparer_comparaison(df):
    """
    Garde les députés dont la circonscription a des indicateurs INSEE et crée :
    - 'outre_mer' : True pour les circonscriptions 97xxx et 98xxx ;
    - 'ecart_age' : âge du député moins âge médian de la population ('dec50').
    L'âge INSEE inclut les enfants : l'écart est positif par construction,
    seule sa variation entre circonscriptions est interprétable.
    """
    d = df[df["indicateur_present"]].copy()
    d["outre_mer"] = d["code_circo"].str[:2].isin(["97", "98"])
    d["ecart_age"] = d["age"] - d["dec50"]
    return d


def correlations_age(d):
    """Corrélation entre âge du député et âge médian de la circonscription."""
    metro = d[~d["outre_mer"]]
    return pd.Series(
        {
            "toutes circonscriptions": d["age"].corr(d["dec50"]),
            "métropole seule": metro["age"].corr(metro["dec50"]),
        }
    )


def graphique_age(d):
    """Âge du député selon l'âge médian de sa circonscription."""
    metro = d[~d["outre_mer"]]
    outre_mer = d[d["outre_mer"]]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(metro["dec50"], metro["age"], alpha=0.5, label="Métropole")
    ax.scatter(
        outre_mer["dec50"], outre_mer["age"], alpha=0.8, color="tab:red",
        label="Outre-mer",
    )
    pente, origine = np.polyfit(metro["dec50"], metro["age"], 1)
    x = np.linspace(metro["dec50"].min(), metro["dec50"].max(), 50)
    ax.plot(x, pente * x + origine, color="black", label="Tendance (métropole)")

    ax.set_xlabel("Âge médian de la population de la circonscription (ans)")
    ax.set_ylabel("Âge du député (ans)")
    ax.set_title("Âge du député et âge de sa circonscription")
    ax.legend()
    fig.tight_layout()
    return fig
def test_correlation_age(d):
    """Corrélation de Pearson et p-value, circonscriptions métropolitaines."""
    metro = d[~d["outre_mer"]]
    r, p = pearsonr(metro["age"], metro["dec50"])
    return r, p
VARIABLES_GENRE = {
    "pop_pole_aav": "Part de la population dans un pôle urbain (%)",
    "pop_rur_non_periu": "Part de la population en commune rurale non périurbaine (%)",
    "nivvie_median_diff": "Niveau de vie médian (€)",
    "tx_pauvrete60_diff": "Taux de pauvreté (%)",
    "act_cad": "Part de cadres parmi les actifs (%)",
    "act_ouv": "Part d'ouvriers parmi les actifs (%)",
    "actdip_BAC5": "Part d'actifs diplômés bac+5 ou plus (%)",
    "taux_chomage": "Taux de chômage (%)",
    "dec50": "Âge médian de la population (ans)",
}


def comparer_genre(d):
    """
    Compare, en métropole, les circonscriptions des députées et des députés
    sur plusieurs indicateurs INSEE : moyennes par genre, écart, et p-value
    du test de Mann-Whitney (comparaison de deux groupes sans hypothèse de
    normalité).
    """
    metro = d[~d["outre_mer"]].copy()
    metro["taux_chomage"] = taux_chomage(metro)
    femmes = metro[metro["genre"] == "Femme"]
    hommes = metro[metro["genre"] == "Homme"]

    lignes = []
    for col, libelle in VARIABLES_GENRE.items():
        f, h = femmes[col].dropna(), hommes[col].dropna()
        lignes.append(
            {
                "indicateur": libelle,
                "moyenne_femmes": f.mean(),
                "moyenne_hommes": h.mean(),
                "ecart": f.mean() - h.mean(),
                "p_value": mannwhitneyu(f, h).pvalue,
            }
        )
    tableau = pd.DataFrame(lignes).set_index("indicateur")
    tableau.attrs["effectifs"] = (len(femmes), len(hommes))
    return tableau
INDICATEURS_INTRA = [
    "act_cad",
    "actdip_BAC5",
    "act_ouv",
    "nivvie_median_diff",
    "pop_pole_aav",
]


def comparer_genre_intra_groupe(d, effectif_min=20):
    """
    Compare, en métropole, les circonscriptions des députées et des députés
    après avoir retiré la moyenne de leur groupe politique : l'écart mesuré
    est donc interne au groupe. Seuls les groupes d'au moins 'effectif_min'
    députés métropolitains sont gardés (moyenne de groupe fragile sinon).
    """
    metro = d[~d["outre_mer"]].copy()
    tailles = metro["groupeAbrev"].value_counts()
    garde = tailles[tailles >= effectif_min].index
    metro = metro[metro["groupeAbrev"].isin(garde)]

    lignes = []
    for col in INDICATEURS_INTRA:
        valeurs = metro[col] - metro.groupby("groupeAbrev")[col].transform("mean")
        f = valeurs[metro["genre"] == "Femme"].dropna()
        h = valeurs[metro["genre"] == "Homme"].dropna()
        lignes.append(
            {
                "indicateur": VARIABLES_GENRE[col],
                "ecart_intra_groupe": f.mean() - h.mean(),
                "p_value": mannwhitneyu(f, h).pvalue,
            }
        )
    tableau = pd.DataFrame(lignes).set_index("indicateur")
    tableau.attrs["groupes"] = sorted(garde)
    tableau.attrs["effectif"] = len(metro)
    return tableau

CSP_LIBELLES = {
    "agr": "Agriculteurs exploitants",
    "art": "Artisans, commerçants, chefs d'entreprise",
    "cad": "Cadres et prof. intellectuelles supérieures",
    "int": "Professions intermédiaires",
    "emp": "Employés",
    "ouv": "Ouvriers",
}


def comparer_csp(deputes, insee_indic):
    """
    Répartition des députés par catégorie socioprofessionnelle comparée à celle
    de la population active (variables INSEE 'act_*', moyenne pondérée par la
    population des circonscriptions, valeurs manquantes ignorées). Seuls les
    députés classés dans une des six catégories sont gardés ('politique',
    'inactif' et 'non_classe' exclus).
    """
    classes = deputes[deputes["csp_depute"].isin(CSP_LIBELLES)]
    part_deputes = classes["csp_depute"].value_counts(normalize=True) * 100

    ind = insee_indic[insee_indic["code_circo"] != "00000"]
    part_pop = {}
    for c in CSP_LIBELLES:
        valides = ind[[f"act_{c}", "pop_légal_19"]].dropna()
        part_pop[c] = np.average(
            valides[f"act_{c}"], weights=valides["pop_légal_19"]
        )

    tableau = pd.DataFrame(
        {"deputes": part_deputes, "population_active": pd.Series(part_pop)}
    ).loc[list(CSP_LIBELLES)]
    tableau["ecart"] = tableau["deputes"] - tableau["population_active"]
    tableau.index = [CSP_LIBELLES[c] for c in tableau.index]
    tableau.attrs["effectif"] = len(classes)
    return tableau.round(1)

def graphique_csp(tableau):
    """Barres horizontales : députés contre population active, par catégorie."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pos = np.arange(len(tableau))
    ax.barh(pos + 0.2, tableau["deputes"], height=0.4, label="Députés")
    ax.barh(
        pos - 0.2, tableau["population_active"], height=0.4,
        label="Population active",
    )
    ax.set_yticks(pos)
    ax.set_yticklabels(tableau.index)
    ax.invert_yaxis()
    ax.set_xlabel("Part (%)")
    ax.set_title("Catégorie socioprofessionnelle : députés et population active")
    ax.legend()
    fig.tight_layout()
    return fig


def part_cadres_par_quartile(d):
    """
    En métropole, part de députés cadres selon le quartile de la circonscription
    en part de cadres parmi les actifs. La p-value est celle d'un test du chi2
    d'indépendance entre quartile et appartenance au groupe des cadres.
    """
    m = d[(~d["outre_mer"]) & d["csp_depute"].isin(CSP_LIBELLES)].copy()
    m["quartile_cadres"] = pd.qcut(
        m["act_cad"], 4,
        labels=["Q1 (moins de cadres)", "Q2", "Q3", "Q4 (plus de cadres)"],
    )
    res = m.groupby("quartile_cadres", observed=True).agg(
        effectif=("id", "count"),
        part_deputes_cadres=("csp_depute", lambda s: (s == "cad").mean() * 100),
        part_cadres_circo=("act_cad", "mean"),
    )
    croise = pd.crosstab(m["quartile_cadres"], m["csp_depute"] == "cad")
    res.attrs["p_value"] = chi2_contingency(croise)[1]
    return res.round(1)

def profil_par_groupe(d, effectif_min=20):
    """
    En métropole, profil moyen des circonscriptions selon le groupe politique du
    député (groupes d'au moins 'effectif_min' députés métropolitains). La p-value
    est celle d'un test de Kruskal-Wallis : la part de cadres des circonscriptions
    diffère-t-elle d'un groupe à l'autre ?
    """
    metro = d[~d["outre_mer"]].copy()
    tailles = metro["groupeAbrev"].value_counts()
    metro = metro[metro["groupeAbrev"].isin(tailles[tailles >= effectif_min].index)]

    tab = metro.groupby("groupeAbrev").agg(
        effectif=("id", "count"),
        part_femmes=("genre", lambda s: (s == "Femme").mean() * 100),
        part_cadres_circo=("act_cad", "mean"),
        niveau_vie_median=("nivvie_median_diff", "mean"),
    ).round(1).sort_values("part_cadres_circo", ascending=False)

    groupes = [g["act_cad"].dropna() for _, g in metro.groupby("groupeAbrev")]
    resultat = kruskal(*groupes)
    n = sum(len(g) for g in groupes)
    tab.attrs["p_kruskal"] = resultat.pvalue
    tab.attrs["h_kruskal"] = resultat.statistic
    tab.attrs["n_kruskal"] = n
    tab.attrs["epsilon2_kruskal"] = resultat.statistic / (n - 1)
    return tab

def correlation_groupes(tab):
    """Corrélation de rang entre part de femmes et part de cadres, par groupe."""
    return spearmanr(tab["part_cadres_circo"], tab["part_femmes"])