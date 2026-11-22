"""
Cartes par circonscription : jointure des contours avec la table
députés + indicateurs INSEE.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

from collecte_contours import charger_contours, gel_contours
from descriptif import preparer_deputes
from extraction_donnees import charger_donnees
from jointures import joindre_deputes_insee
from professions import ajouter_categorie_job


PREFIXES_OUTRE_MER = {
    "ZA": "971",  # Guadeloupe
    "ZB": "972",  # Martinique
    "ZC": "973",  # Guyane
    "ZD": "974",  # La Réunion
    "ZS": "975",  # Saint-Pierre-et-Miquelon
    "ZM": "976",  # Mayotte
}

OUTRE_MER = [
    ("971", "Guadeloupe"),
    ("972", "Martinique"),
    ("973", "Guyane"),
    ("974", "La Réunion"),
    ("975", "St-Pierre-et-Miq."),
    ("976", "Mayotte"),
]

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

CSP_DEPUTES = {
    "cad": ("Cadres et prof. intell. sup.", "#1f78b4"),
    "int": ("Professions intermédiaires", "#33a02c"),
    "art": ("Artisans, commerçants, chefs d'ent.", "#ff7f00"),
    "emp": ("Employés", "#e31a1c"),
    "ouv": ("Ouvriers", "#6a3d9a"),
    "agr": ("Agriculteurs exploitants", "#b15928"),
    "autres": ("Autres / inactifs / politique", "#a6cee3"),
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
    """Contours joints aux députés et aux indicateurs INSEE."""
    gel_contours()
    deputes, insee_indic, _, _ = charger_donnees()
    insee_indic = insee_indic.copy()
    insee_indic["part_femmes"] = (
        (insee_indic["actemp_hom"] - insee_indic["actemp"])
        / (insee_indic["actemp_hom"] - insee_indic["actemp_fem"])
        * 100
    )
    deputes = ajouter_categorie_job(preparer_deputes(deputes))
    df = joindre_deputes_insee(preparer_deputes(deputes), insee_indic)
    contours = ajouter_code_circo(charger_contours())
    colonnes = ["code_circo", "genre", "groupeAbrev", "age", "csp_depute",
                "act_cad", "nivvie_median_diff", "dec50", "part_femmes"]
    return contours.merge(
        df[colonnes], on="code_circo", how="left", validate="one_to_one"
    )


def _nettoyer_encart(ax, titre, couleur="0.4"):
    """Retire les graduations et les labels Longitude/Latitude d'un encart."""
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(titre, fontsize=8, color=couleur)
    for cote in ax.spines.values():
        cote.set_edgecolor(couleur)
        cote.set_linewidth(1)


def ajouter_encarts(fig, ax_metro, carte, plot_func):
    """Ajoute un zoom sur Paris/Petite Couronne et les encarts d'outre-mer."""
    # Dégage de l'espace à gauche (Paris) et en bas (Outre-mer)
    ax_metro.set_position([0.22, 0.16, 0.62, 0.75])

    # 1. Encart Paris et petite couronne (75, 92, 93, 94) à gauche
    paris = carte[carte["code_circo"].str[:2].isin(["75", "92", "93", "94"])]
    xmin, ymin, xmax, ymax = paris.total_bounds
    ax_metro.add_patch(Rectangle(
        (xmin - 0.05, ymin - 0.05), xmax - xmin + 0.1, ymax - ymin + 0.1,
        fill=False, edgecolor="crimson", linewidth=1
    ))
    ax_paris = fig.add_axes([0.03, 0.58, 0.19, 0.22])
    plot_func(paris, ax_paris)
    _nettoyer_encart(ax_paris, "Paris & petite couronne", couleur="crimson")

    # 2. Encarts outre-mer en bas de la figure
    for i, (dep, nom) in enumerate(OUTRE_MER):
        drom = carte[carte["code_circo"].str[:3] == dep]
        if len(drom) == 0:
            continue
        ax_om = fig.add_axes([0.04 + i * 0.155, 0.02, 0.13, 0.11])
        plot_func(drom, ax_om)
        _nettoyer_encart(ax_om, nom)


def carte_indicateur(carte, colonne, titre, cmap="viridis", vmax=None, unite="%"):
    """Carte de la France métropolitaine colorée par un indicateur."""
    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    vmin = carte[colonne].min()
    vmax_eff = carte[colonne].max() if vmax is None else vmax

    fig, ax = plt.subplots(figsize=(10, 8.5))
    metro.plot(
        column=colonne, cmap=cmap, legend=True, edgecolor="white",
        linewidth=0.2, ax=ax, vmin=vmin, vmax=vmax_eff,
        legend_kwds={"label": unite} if unite else {},
        missing_kwds={"color": "lightgrey", "label": "Pas de données"},
    )
    fig.suptitle(titre, fontsize=13, y=0.97)
    if vmax is not None:
        fig.text(0.5, 0.935, f"Échelle plafonnée à {vmax} {unite}".strip(),
                 ha="center", fontsize=9, color="gray")
    ax.set_axis_off()

    ajouter_encarts(fig, ax, carte, lambda df, a: df.plot(
        column=colonne, cmap=cmap, vmin=vmin, vmax=vmax_eff,
        edgecolor="white", linewidth=0.2, ax=a,
        missing_kwds={"color": "lightgrey"},
    ))
    return fig


def carte_genre(carte):
    """Carte de la France métropolitaine : genre du député par circonscription."""
    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    fig, ax = plt.subplots(figsize=(10, 8.5))
    metro.plot(
        column="genre", categorical=True, legend=True, edgecolor="white",
        linewidth=0.2, ax=ax, cmap="Set2",
        missing_kwds={"color": "lightgrey", "label": "Pas de député"},
    )
    fig.suptitle("Genre du député par circonscription", fontsize=13, y=0.97)
    ax.set_axis_off()

    ajouter_encarts(fig, ax, carte, lambda df, a: df.plot(
        column="genre", categorical=True, cmap="Set2",
        edgecolor="white", linewidth=0.2, ax=a,
        missing_kwds={"color": "lightgrey"},
    ))
    return fig

def carte_csp(carte):
    """Carte par circonscription : catégorie socioprofessionnelle du député."""
    carte = carte.copy()
    code_csp = carte["csp_depute"].where(
        carte["csp_depute"].isin(["cad", "int", "art", "emp", "ouv", "agr"]),
        "autres",
    )
    code_csp = code_csp.where(carte["csp_depute"].notna())
    couleurs = {k: c for k, (_, c) in CSP_DEPUTES.items()}
    carte["couleur"] = code_csp.map(couleurs).fillna("lightgrey")

    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    fig, ax = plt.subplots(figsize=(10, 8.5))
    metro.plot(color=metro["couleur"], edgecolor="white", linewidth=0.2, ax=ax)

    legende = [Patch(color=c, label=lbl) for lbl, c in CSP_DEPUTES.values()]
    legende.append(Patch(color="lightgrey", label="Pas de député"))
    ax.legend(handles=legende, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.suptitle("Catégorie socioprofessionnelle du député par circonscription", fontsize=13, y=0.97)
    ax.set_axis_off()

    ajouter_encarts(fig, ax, carte, lambda df, a: df.plot(
        color=df["couleur"], edgecolor="white", linewidth=0.2, ax=a
    ))
    return fig


def carte_groupes(carte):
    """Carte de la France métropolitaine : groupe politique du député."""
    carte = carte.copy()
    groupe = carte["groupeAbrev"].where(
        carte["groupeAbrev"].isin(COULEURS_GROUPES), "Autres"
    )
    groupe = groupe.where(carte["groupeAbrev"].notna())
    carte["couleur"] = groupe.map(COULEURS_GROUPES).fillna("lightgrey")

    metro = carte[~carte["code_circo"].str[:2].isin(["97", "98", "99"])]
    fig, ax = plt.subplots(figsize=(10, 8.5))
    metro.plot(color=metro["couleur"], edgecolor="white", linewidth=0.2, ax=ax)

    legende = [Patch(color=c, label=g) for g, c in COULEURS_GROUPES.items()]
    legende.append(Patch(color="lightgrey", label="Pas de député"))
    ax.legend(handles=legende, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.suptitle("Groupe politique du député par circonscription", fontsize=13, y=0.97)
    ax.set_axis_off()

    ajouter_encarts(fig, ax, carte, lambda df, a: df.plot(
        color=df["couleur"], edgecolor="white", linewidth=0.2, ax=a
    ))
    return fig


if __name__ == "__main__":
    gel_contours()
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

    for nom, fig in [
        ("carte_cadres.png", carte_indicateur(
            carte, "act_cad", "Part de cadres parmi les actifs (%), par circonscription"
        )),
        ("carte_csp_deputes.png", carte_csp(carte)),
        ("carte_part_femmes.png", carte_indicateur(
            carte, "part_femmes", "Part de femmes dans la population (%), par circonscription",
            cmap="Purples"
        )),
        ("carte_genre.png", carte_genre(carte)),
        ("carte_groupes.png", carte_groupes(carte)),
    ]:
        fig.savefig(nom, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print("Carte enregistrée :", nom)