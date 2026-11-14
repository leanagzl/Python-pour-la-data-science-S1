"""
Statistiques descriptives sur les députés et les indicateurs INSEE.
"""

import pandas as pd
import matplotlib.pyplot as plt

COLONNES_NUM = [
    "nombreMandats",
    "scoreParticipation",
    "scoreParticipationSpecialite",
    "scoreLoyaute",
    "scoreMajorite",
]


def preparer_deputes(df):
    """
    Convertit en numérique les colonnes lues en texte et crée les variables
    'genre' (à partir de 'civ') et 'experience_ans' (à partir de '9 ans').
    """
    df = df.copy()
    for col in COLONNES_NUM:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["experience_ans"] = pd.to_numeric(
        df["experienceDepute"].str.extract(r"(\d+)")[0], errors="coerce"
    )
    df["genre"] = df["civ"].map({"M.": "Homme", "Mme": "Femme"})
    return df


def tableau_groupes(df):
    """Effectif, âge moyen et part de femmes par groupe politique."""
    return (
        df.groupby("groupeAbrev")
        .agg(
            effectif=("id", "count"),
            age_moyen=("age", "mean"),
            part_femmes=("genre", lambda s: (s == "Femme").mean() * 100),
        )
        .round(1)
        .sort_values("effectif", ascending=False)
    )


def valeurs_manquantes(df):
    """Nombre et part de valeurs manquantes, pour les colonnes concernées."""
    nb = df.isna().sum()
    tab = pd.DataFrame({"nb": nb, "pct": (nb / len(df) * 100).round(1)})
    return tab[tab["nb"] > 0].sort_values("nb", ascending=False)


def graphique_deputes(df):
    """Répartition des députés par groupe et distribution de l'âge."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    effectifs = df["groupeAbrev"].value_counts()
    axes[0].barh(effectifs.index[::-1], effectifs.values[::-1])
    axes[0].set_xlabel("Nombre de députés")
    axes[0].set_title("Députés par groupe politique")

    axes[1].hist(df["age"].dropna(), bins=15)
    axes[1].set_xlabel("Âge (ans)")
    axes[1].set_ylabel("Nombre de députés")
    axes[1].set_title("Distribution de l'âge des députés")

    fig.tight_layout()
    return fig


def graphique_insee(df):
    """Dispersion de trois indicateurs INSEE entre circonscriptions."""
    variables = {
        "actcho": "Part de la population au chômage (%)",
        "nivvie_median_diff": "Niveau de vie médian (€)",
        "age_moyen": "Âge moyen de la population (ans)",
    }
    donnees = df[df["indicateur_present"]]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (col, titre) in zip(axes, variables.items()):
        ax.hist(donnees[col].dropna(), bins=20)
        ax.set_xlabel(titre)
        ax.set_ylabel("Nombre de circonscriptions")
    fig.tight_layout()
    return fig1