"""
Comparaison entre le profil des députés et celui de leur circonscription.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, pearsonr

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