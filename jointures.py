"""
Jointure entre les députés actifs et les indicateurs INSEE par circonscription.
"""

from extraction_donnees import charger_donnees, DATA_DIR


def joindre_deputes_insee(deputes, insee_indic):
    """
    Joint les députés aux indicateurs INSEE sur la clé 'code_circo'.

    Choix documentés :
    - la ligne '00000' d'INSEE n'est pas une circonscription (total) : exclue ;
    - jointure à gauche : on garde tous les députés, y compris les 11
      circonscriptions des Français de l'étranger (99001 à 99011), pour
      lesquelles l'INSEE ne publie pas d'indicateurs (valeurs manquantes).

    Retour
    ------
    df : pandas.DataFrame
        Table jointe, avec une colonne 'indicateur_present' (True si l'INSEE
        a des données pour la circonscription du député).
    """
    insee = insee_indic[insee_indic["code_circo"] != "00000"].copy()

    # Colonnes en commun hors clé : on préfixe celles de l'INSEE pour éviter les collisions
    communes = (set(deputes.columns) & set(insee.columns)) - {"code_circo"}
    insee = insee.rename(columns={c: f"insee_{c}" for c in communes})

    df = deputes.merge(
        insee,
        on="code_circo",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    df["indicateur_present"] = df["_merge"] == "both"
    return df.drop(columns="_merge")


if __name__ == "__main__":
    deputes, insee_indic, insee_compo, dico_insee = charger_donnees()
    df = joindre_deputes_insee(deputes, insee_indic)

    print("Forme de la table jointe :", df.shape)
    print("Députés avec indicateurs INSEE :", int(df["indicateur_present"].sum()))
    print("Députés sans indicateurs INSEE :", int((~df["indicateur_present"]).sum()))
    print(sorted(df.loc[~df["indicateur_present"], "code_circo"]))

    sortie = DATA_DIR / "data_clean" / "deputes_insee.parquet"
    df.to_parquet(sortie, index=False)
    print("Table jointe sauvegardée :", sortie)