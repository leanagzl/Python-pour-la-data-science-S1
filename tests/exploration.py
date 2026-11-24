from src.collecte.extraction_donnees import charger_donnees

deputes, insee_indic, insee_compo, dico_insee = charger_donnees()

print("Colonnes députés :", deputes.columns.tolist())
print()
print(deputes[["departementCode", "circo", "code_circo"]].head(10))
print()
print(insee_indic[["circo", "code_circo"]].head(10))
print()

codes_d = set(deputes["code_circo"])
codes_i = set(insee_indic["code_circo"])
print("Nb codes députés :", len(codes_d))
print("Nb codes INSEE :", len(codes_i))
print("Députés sans match INSEE :", sorted(codes_d - codes_i))
print("INSEE sans député :", sorted(codes_i - codes_d))