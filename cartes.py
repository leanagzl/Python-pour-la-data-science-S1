"""
Cartes par circonscription : jointure des contours avec la table
députés + indicateurs INSEE
"""

import matplotlib.pyplot as plt

from collecte_contours import charger_contours
from descriptif import preparer_deputes
from extraction_donnees import charger_donnees
from jointures import joindre_deputes_insee


PREFIXES_OUTRE_MER = {
    "ZA": "971",  # Guadeloupe
    "ZB": "972",  # Martinique
    "ZC": "973",  # Guyane
    "ZD": "974",  # La Réunion
    "ZS": "975",  # Saint-Pierre-et-Miquelon
    "ZM": "976",  # Mayotte
}


def ajouter_code_circo(contours):
    """
    Construit 'code_circo' au format INSEE à partir des contours :
    département (2) + circo (3) en métropole, département (3) + circo (2)
    en outre-mer. Les contours codent l'outre-mer par 'ZA', 'ZB'... qu'on
    traduit en codes départementaux (971, 972...).
    """
    g = contours.copy()
    dep = g["codeDepartement"].str.strip().str.upper()
    dep = dep.replace(PREFIXES_OUTRE_MER)
    circo = g["codeCirconscription"].str.strip().str[-2:]
    g["code_circo"] = [
        d + c if len(d) == 3 else d + c.zfill(3) for d, c in zip(dep, circo)
    ]
    return g

def preparer_carte():
    """Contours joints aux députés et aux indicateurs INSEE"""
    deputes, insee_indic, _, _ = charger_donnees()
    df = joindre_deputes_insee(preparer_deputes(deputes), insee_indic)
    contours = ajouter_code_circo(charger_contours())
    colonnes = ["code_circo", "genre", "groupeAbrev", "age",
                "act_cad", "nivvie_median_diff", "dec50"]
    return contours.merge(
        df[colonnes], on="code_circo", how="left", validate="one_to_one"
    )


def carte_indicateur(carte, colonne, titre, cmap="viridis", vmax=None):
    """Carte de la France métropolitaine colorée par un indicateur."""
    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    fig, ax = plt.subplots(figsize=(8, 8))
    metro.plot(
        column=colonne, cmap=cmap, legend=True, edgecolor="white",
        linewidth=0.2, ax=ax, vmax=vmax,
        missing_kwds={"color": "lightgrey", "label": "Pas de données"},
    )
    ax.set_title(titre)
    if vmax is not None:
        ax.text(0.5, 0.97, f"Échelle plafonnée à {vmax} %",
                transform=ax.transAxes, ha="center", fontsize=9, color="gray")
    ax.set_axis_off()
    fig.tight_layout()
    return fig

def carte_genre(carte):
    """Carte de la France métropolitaine : genre du député par circonscription."""
    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    fig, ax = plt.subplots(figsize=(8, 8))
    metro.plot(
        column="genre", categorical=True, legend=True, edgecolor="white",
        linewidth=0.2, ax=ax, cmap="Set2",
        missing_kwds={"color": "lightgrey", "label": "Pas de député"},
    )
    ax.set_title("Genre du député par circonscription (métropole)")
    ax.set_axis_off()
    fig.tight_layout()
    return fig

from matplotlib.patches import Patch

COULEURS_GROUPES = {
    "RN": "#1f3b73",
    "EPR": "#f2c94c",
    "LFI-NFP": "#c0392b",
    "SOC": "#e75480",
    "DR": "#4a90d9",
    "ECOS": "#2e8b57",
    "DEM": "#f08a24",
    "HOR": "#8fd3f4",
    "Autres": "#8e6bbf",
}


def carte_groupes(carte):
    """Carte de la France métropolitaine : groupe politique du député."""
    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])].copy()
    groupe = metro["groupeAbrev"].where(
        metro["groupeAbrev"].isin(COULEURS_GROUPES), "Autres"
    )
    groupe = groupe.where(metro["groupeAbrev"].notna())
    metro["couleur"] = groupe.map(COULEURS_GROUPES).fillna("lightgrey")

    fig, ax = plt.subplots(figsize=(8, 8))
    metro.plot(color=metro["couleur"], edgecolor="white", linewidth=0.2, ax=ax)

    legende = [Patch(color=c, label=g) for g, c in COULEURS_GROUPES.items()]
    legende.append(Patch(color="lightgrey", label="Pas de député"))
    ax.legend(handles=legende, loc="upper right", fontsize=8)
    ax.set_title("Groupe politique du député par circonscription (métropole)")
    ax.set_axis_off()
    fig.tight_layout()
    return fig

if __name__ == "__main__":
    deputes, insee_indic, _, _ = charger_donnees()
    contours = ajouter_code_circo(charger_contours())

    codes_c = set(contours["code_circo"])
    codes_i = set(insee_indic.loc[insee_indic["code_circo"] != "00000", "code_circo"])
    print("Exemples contours :", contours["code_circo"].head(5).tolist())
    print("Doublons de clé dans les contours :", contours["code_circo"].duplicated().sum())
    print("Contours sans INSEE :", sorted(codes_c - codes_i))
    print("INSEE sans contours :", sorted(codes_i - codes_c))

    carte = preparer_carte()
    print("Circonscriptions avec indicateur :", int(carte["act_cad"].notna().sum()))

    fig = carte_indicateur(
        carte, "act_cad", "Part de cadres parmi les actifs (%), par circonscription"
    )
    fig.savefig("carte_cadres.png", dpi=200, bbox_inches="tight")
    plt.show()
