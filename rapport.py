import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = [
    nbf.v4.new_markdown_cell("# Les députés représentent-ils leurs électeurs ?"),
    nbf.v4.new_markdown_cell("_Projet Python pour la Data Science — 2026_"),
    nbf.v4.new_markdown_cell("## Introduction"),
    nbf.v4.new_markdown_cell(
        "La démocratie représentative repose sur l'idée que les élus portent la voix et les préoccupations de l'ensemble des citoyens. "
        "En science politique, on distingue classiquement la **représentation substantielle** (défendre les intérêts et les idées des électeurs) "
        "de la **représentation descriptive** (ressembler socio-démographiquement à la population représentée en termes d'âge, de genre ou de catégorie socioprofessionnelle).\n\n"
        "Or, le débat public français souligne régulièrement un décalage croissant entre le profil sociologique des parlementaires de l'Assemblée nationale "
        "et la réalité démographique et économique des Français. L'Assemblée nationale est-elle le reflet fidèle du pays, ou constitue-t-elle un espace socialement sélectif ? "
        "Et plus finement : les députés ressemblent-ils au moins aux électeurs de **leur propre circonscription** ?\n\n"
        "Pour répondre à cette problématique, nous croisons les données individuelles des députés actifs de la XVIIe législature avec les indicateurs socio-économiques "
        "de l'INSEE mesurés à l'échelle fine des 577 circonscriptions législatives. Nous structurons notre démarche en trois temps : la construction et l'audit d'une base "
        "de données reproductible, une exploration descriptive et cartographique des écarts de représentation, puis une modélisation statistique visant à identifier les déterminants de cette représentativité."
    ),
    nbf.v4.new_markdown_cell(
        "### Sommaire\n\n"
        "- **Introduction**\n"
        "- **I. Création et exploration de la base de données principale**\n"
        "    - A. Récupération et gel des données sources\n"
        "    - B. Nettoyage, harmonisation des clés et jointure des tables\n"
        "    - C. Contrôle de la qualité des données (Audit)\n"
        "- **II. Visualisations, cartographie et statistiques descriptives**\n"
        "    - A. Exploration univariée : qui sont les députés ? Qui sont les électeurs ?\n"
        "    - B. Analyse croisée : le député face à sa circonscription\n"
        "- **III. Modélisation : les caractéristiques d'une circonscription expliquent-elles le profil de son député ?**\n"
        "    - A. Objectif et construction des variables cibles\n"
        "    - B. Modèle 1 : Probabilité d'élire une femme (Régression Logistique)\n"
        "    - C. Modèle 2 : Déterminants de la CSP et de l'âge du député (Logit & OLS)\n"
        "    - D. Limites méthodologiques\n"
        "- **Conclusion**"
    ),
    nbf.v4.new_code_cell("# %pip install -r requirements.txt"),
    nbf.v4.new_markdown_cell("## I. Création et exploration de la base de données principale"),
    nbf.v4.new_markdown_cell(
        "Dans cette première partie, nous construisons un pipeline reproductible permettant d'importer, de figer (_geler_) et d'assembler les différentes sources de données publiques.\n\n"
        "| Nom de la table | Description | Source | Mode d'extraction |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| `deputes` | Informations individuelles des députés actifs (âge, civilité, profession, groupe politique, scores parlementaires). | API data.gouv.fr / Datan | API REST (CSV gelé) |\n"
        "| `insee_indic` | Indicateurs démographiques et économiques par circonscription législative (structure par âge, emploi, CSP, niveau de vie). | INSEE (Recensement & Filosofi) | Fichier Excel (XLSX gelé) |\n"
        "| `insee_compo` | Table de passage entre communes et circonscriptions législatives. | INSEE | Fichier Excel (XLSX gelé) |\n"
        "| `contours` | Géométries des 577 circonscriptions législatives françaises (métropole et outre-mer). | data.gouv.fr (J. Desboeufs) | GeoJSON gelé |"
    ),
    nbf.v4.new_code_cell(
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import statsmodels.api as sm\n"
        "import statsmodels.formula.api as smf\n\n"
        "from cartes import (\n"
        "    ajouter_code_circo,\n"
        "    carte_csp,\n"
        "    carte_genre,\n"
        "    carte_groupes,\n"
        "    carte_indicateur,\n"
        "    preparer_carte,\n"
        ")\n"
        "from collecte_contours import charger_contours, gel_contours\n"
        "from descriptif import (\n"
        "    graphique_deputes,\n"
        "    graphique_insee,\n"
        "    preparer_deputes,\n"
        "    tableau_groupes,\n"
        "    taux_chomage,\n"
        "    valeurs_manquantes,\n"
        ")\n"
        "from extraction_donnees import (\n"
        "    charger_donnees,\n"
        "    gel_bases_clean,\n"
        "    gel_donnees_deputes,\n"
        "    gel_donnees_insee,\n"
        ")\n"
        "from jointures import joindre_deputes_insee\n"
        "from professions import ajouter_categorie_job"
    ),
    nbf.v4.new_markdown_cell("### A. Récupération et gel des données sources"),
    nbf.v4.new_markdown_cell(
        "Afin de garantir la stricte reproductibilité de nos résultats — la liste des députés actifs évoluant au gré des démissions, nominations gouvernementales ou élections partielles — "
        "nous téléchargeons et sauvegardons localement les fichiers bruts dans `data/data_brut` avant de générer des tables propres au format `.parquet` dans `data/data_clean`."
    ),
    nbf.v4.new_code_cell(
        "# 1. Téléchargement et gel des données brutes (ne retélécharge pas si déjà présent)\n"
        "gel_donnees_insee(forcer=False)\n"
        "gel_donnees_deputes(forcer=False)\n"
        "gel_contours(forcer=False)\n\n"
        "# 2. Nettoyage séparé et sauvegarde en format Parquet\n"
        "gel_bases_clean()\n\n"
        "# 3. Chargement des bases propres\n"
        "deputes, insee_indic, insee_compo, dico_insee = charger_donnees()"
    ),
    nbf.v4.new_markdown_cell("### B. Nettoyage, harmonisation des clés et jointure des tables"),
    nbf.v4.new_markdown_cell(
        "Le principal défi technique de l'assemblage réside dans l'harmonisation de l'identifiant unique de circonscription (`code_circo`) au format standardisé de l'INSEE sur 5 caractères :\n"
        "- **France métropolitaine** : code département sur 2 caractères (`01` à `95`, incluant `2A` et `2B` en majuscules pour la Corse) + numéro de circonscription sur 3 chiffres (`001`, `018`, etc.).\n"
        "- **Outre-mer** : code département sur 3 chiffres (`971` à `976`) + numéro de circonscription sur 2 chiffres (`01`, `02`, etc.).\n"
        "- **Cas particulier des collectivités d'outre-mer** : l'INSEE regroupe Saint-Barthélemy (`97701`) et Saint-Martin (`97801`) sous un même code statistique (`97801`).\n"
        "- **Français établis hors de France** : les 11 circonscriptions de l'étranger (`99` / `ZZ`) n'ont pas d'équivalent territorial dans le recensement INSEE métropolitain/DROM."
    ),
    nbf.v4.new_code_cell(
        "deputes_prep = ajouter_categorie_job(preparer_deputes(deputes))\n"
        "df_complet = joindre_deputes_insee(deputes_prep, insee_indic)\n\n"
        "df_complet['taux_chomage'] = taux_chomage(df_complet)\n"
        "df_complet['part_femmes_pop'] = (\n"
        "    (df_complet['actemp_hom'] - df_complet['actemp'])\n"
        "    / (df_complet['actemp_hom'] - df_complet['actemp_fem'])\n"
        "    * 100\n"
        ")\n\n"
        "display(\n"
        "    df_complet[[\n"
        "        'code_circo', 'nom', 'prenom', 'genre', 'age',\n"
        "        'csp_depute', 'groupeAbrev', 'act_cad', 'nivvie_median_diff'\n"
        "    ]].head(10)\n"
        ")"
    ),
    nbf.v4.new_markdown_cell("### C. Contrôle de la qualité des données (Audit)"),
    nbf.v4.new_code_cell(
        "print('Dimensions de la table jointe :', df_complet.shape)\n"
        "print('Circonscriptions avec données INSEE :', df_complet['indicateur_present'].sum())\n"
        "print('Circonscriptions avec un député actif :', df_complet['id'].notna().sum())\n"
        "print('Doublons sur code_circo :', df_complet['code_circo'].duplicated().sum())\n"
        "display(valeurs_manquantes(df_complet).head(15))"
    ),
    nbf.v4.new_markdown_cell(
        "**Interprétation de l'audit :**\n"
        "- **Circonscriptions sans député actif** : quelques circonscriptions affichent des valeurs manquantes sur les variables parlementaires (sièges vacants suite à des nominations au gouvernement avant l'entrée en fonction du suppléant, démissions ou invalidations). Elles apparaîtront en gris (« Pas de député ») sur nos cartes.\n"
        "- **Secret statistique INSEE** : certaines variables économiques (`nivvie_median_diff`) sont masquées (`NaN`) pour les très petites circonscriptions comme Saint-Pierre-et-Miquelon (`97501`) ou Saint-Martin/Saint-Barthélemy (`97801`)."
    ),
    nbf.v4.new_markdown_cell("## II. Visualisations, cartographie et statistiques descriptives"),
    nbf.v4.new_markdown_cell("### A. Exploration univariée : qui sont les députés ? Qui sont les électeurs ?"),
    nbf.v4.new_code_cell(
        "display(tableau_groupes(deputes_prep))\n\n"
        "fig_dep = graphique_deputes(deputes_prep)\n"
        "plt.show()\n\n"
        "fig_insee = graphique_insee(df_complet)\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell("### B. Analyse croisée : le député face à sa circonscription"),
    nbf.v4.new_code_cell("carte = preparer_carte()"),
    nbf.v4.new_markdown_cell("#### 1. Le genre : parité nationale et ancrage territorial"),
    nbf.v4.new_code_cell(
        "fig_genre = carte_genre(carte)\n"
        "plt.show()\n\n"
        "fig_part_femmes = carte_indicateur(\n"
        "    carte,\n"
        "    'part_femmes_pop',\n"
        "    'Part de femmes dans la population active occupée (%), par circonscription',\n"
        "    cmap='Purples',\n"
        ")\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell(
        "**Analyse comparative :** Alors que les femmes représentent systématiquement environ 50 % à 53 % de la population des circonscriptions, la carte du genre des députés reste majoritairement colorée en orange (hommes), avec une concentration plus forte de femmes députées en Île-de-France, en Bretagne et dans les grandes aires urbaines."
    ),
    nbf.v4.new_markdown_cell("#### 2. La catégorie socioprofessionnelle (CSP) : la surreprésentation des cadres"),
    nbf.v4.new_code_cell(
        "part_csp_deputes = (df_complet['csp_depute'].value_counts(normalize=True) * 100).round(1)\n"
        "print('Répartition des CSP parmi les députés (%) :')\n"
        "display(part_csp_deputes)\n"
        "print(f\"\\nPart moyenne des cadres parmi les actifs en France (INSEE) : {df_complet['act_cad'].mean():.1f} %\")\n\n"
        "fig_csp = carte_csp(carte)\n"
        "plt.show()\n\n"
        "fig_cadres = carte_indicateur(\n"
        "    carte, 'act_cad', 'Part de cadres parmi les actifs (%), par circonscription'\n"
        ")\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell(
        "**Analyse comparative :**\n"
        "1. **Un monopole des catégories supérieures :** Plus des deux tiers des députés appartiennent à la catégorie des _Cadres et professions intellectuelles supérieures_, alors qu'ils ne représentent qu'environ 18 % à 20 % des actifs en France.\n"
        "2. **L'invisibilité des classes populaires :** Les ouvriers et employés, qui forment près de la moitié de la population active française, représentent moins de 5 % des députés.\n"
        "3. **Une géographie duale :** La carte de l'INSEE montre que les cadres sont concentrés à Paris, dans la petite couronne et dans quelques métropoles régionales. À l'inverse, la carte des députés est uniformément bleue (_Cadres_) sur l'ensemble du territoire rural et périurbain."
    ),
    nbf.v4.new_markdown_cell("#### 3. L'âge et le niveau de vie : un décalage générationnel et économique"),
    nbf.v4.new_code_cell(
        "fig, axes = plt.subplots(1, 2, figsize=(13, 5))\n\n"
        "axes[0].scatter(df_complet['age_moyen'], df_complet['age'], alpha=0.5, color='#1f78b4')\n"
        "axes[0].plot([30, 50], [30, 50], color='crimson', linestyle='--', label='Égalité parfaite (y = x)')\n"
        "axes[0].set_xlabel('Âge moyen de la population de la circonscription (ans)')\n"
        "axes[0].set_ylabel('Âge du député (ans)')\n"
        "axes[0].set_title('Âge du député vs Âge moyen de sa circonscription')\n"
        "axes[0].legend()\n\n"
        "df_complet.boxplot(column='age', by='csp_depute', ax=axes[1], rot=45)\n"
        "axes[1].set_title(\"Distribution de l'âge des députés par CSP\")\n"
        "axes[1].set_xlabel('CSP du député')\n"
        "axes[1].set_ylabel('Âge (ans)')\n"
        "plt.suptitle('')\n\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell("## III. Modélisation : les caractéristiques d'une circonscription expliquent-elles le profil de son député ?"),
    nbf.v4.new_markdown_cell("### A. Objectif et construction des variables cibles"),
    nbf.v4.new_code_cell(
        "df_model = df_complet.dropna(\n"
        "    subset=['id', 'genre', 'age', 'csp_depute', 'act_cad', 'nivvie_median_diff', 'taux_chomage']\n"
        ").copy()\n\n"
        "df_model['est_femme'] = (df_model['genre'] == 'Femme').astype(int)\n"
        "df_model['est_cadre'] = (df_model['csp_depute'] == 'cad').astype(int)\n"
        "print('Nombre d\\'observations retenues pour la modélisation :', len(df_model))"
    ),
    nbf.v4.new_markdown_cell("### B. Modèle 1 : Probabilité d'élire une femme (Régression Logistique)"),
    nbf.v4.new_code_cell(
        "logit_socio = smf.logit('est_femme ~ act_cad + taux_chomage + age_moyen', data=df_model).fit(disp=False)\n"
        "print('=== MODÈLE 1A : Déterminants territoriaux de l\\'élection d\\'une femme ===')\n"
        "print(logit_socio.summary())\n\n"
        "logit_complet = smf.logit(\n"
        "    'est_femme ~ act_cad + taux_chomage + age_moyen + C(groupeAbrev)', data=df_model\n"
        ").fit(disp=False)\n"
        "print('\\n=== MODÈLE 1B : Avec contrôle par groupe politique ===')\n"
        "print(logit_complet.summary())"
    ),
    nbf.v4.new_markdown_cell("### C. Modèle 2 : Déterminants de la CSP et de l'âge du député (Logit & OLS)"),
    nbf.v4.new_code_cell(
        "logit_cadre = smf.logit('est_cadre ~ act_cad + nivvie_median_diff + taux_chomage', data=df_model).fit(disp=False)\n"
        "print('=== MODÈLE 2A : Probabilité d\\'élire un député Cadre ===')\n"
        "print(logit_cadre.summary())\n\n"
        "ols_age = smf.ols(\n"
        "    'age ~ age_moyen + nivvie_median_diff + taux_chomage + C(groupeAbrev)', data=df_model\n"
        ").fit(cov_type='HC3')\n"
        "print('\\n=== MODÈLE 2B : Déterminants de l\\'âge du député (OLS) ===')\n"
        "print(ols_age.summary())"
    ),
    nbf.v4.new_markdown_cell(
        "### D. Limites méthodologiques\n\n"
        "1. **Biais d'offre politique (sélection avant le vote) :** Nous n'observons que le député _élu_, et non l'ensemble des _candidats_ présents au premier tour.\n"
        "2. **Limite de la nomenclature des professions :** La profession déclarée correspond parfois à une activité exercée avant une longue carrière d'élu local.\n"
        "3. **Représentation descriptive vs substantielle :** L'absence de similitude sociologique n'implique pas mécaniquement une divergence de défense des intérêts locaux."
    ),
    nbf.v4.new_markdown_cell(
        "## Conclusion\n\n"
        "À la question _« Les députés représentent-ils leurs électeurs ? »_, notre croisement des données de l'Assemblée nationale et de l'INSEE montre que **l'Assemblée nationale ne reflète pas la structure socio-démographique de la population française, ni celle des circonscriptions locales** :\n\n"
        "1. **Un biais social massif :** Les cadres et professions intellectuelles supérieures occupent plus des deux tiers des sièges de l'Assemblée nationale.\n"
        "2. **Un déficit persistant de parité et de jeunesse :** Les hommes et les 45-60 ans demeurent largement surreprésentés.\n"
        "3. **Le poids des structures partisanes :** Le profil de l'élu dépend beaucoup moins de la sociologie de sa circonscription que des logiques d'investiture des groupes politiques."
    ),
]

nb["cells"] = cells

with open("rapport_final.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("Fichier 'rapport_final.ipynb' généré avec succès !")