from flask import Flask, render_template, request
import pandas as pd
import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

# Charger les données une fois
DATA_PATH = "dataset_corrige.csv"
df = pd.read_csv(DATA_PATH, dtype={"matricule": str})
df["sexe"] = (
    df["sexe"]
    .astype(str)
    .str.strip()
    .str.lower()
    .replace({"m": "homme", "f": "femme", "h": "homme"})
)

df.columns = df.columns.str.strip().str.lower()
df["matricule"] = (
    df["matricule"].astype(str).str.strip().str.replace(".0", "", regex=False)
)

# Dictionnaire test + labels
test_labels = {
    "resul gain": "Gainage",
    "resul killy": "Killy",
    "resul ll": "Luc Léger",
    "resul pompes": "Pompes",
    "resul souplesse": "Souplesse",
    "resul tractions": "Tractions",
}

# Associer test avec colonne de niveau
niveau_cols = {
    "resul gain": "niveau gain",
    "resul killy": "niv killy",
    "resul ll": "niv ll",
    "resul pompes": "niv pompes",
    "resul souplesse": "niv souplesse",
    "resul tractions": "niv tractions",
}


# Fonction pour convertir matplotlib en base64
def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_alertes_sante_evolution(agent_data):
    alertes_sante = []
    alertes_sante_details = []

    # --- IMC ---
    if "imc" in agent_data.columns:
        imc_data = agent_data[["année", "imc"]].dropna()
        imc_data = imc_data[imc_data["année"].between(2019, 2024)]
        imc_data = imc_data.sort_values("année")
        if len(imc_data) >= 2:

            def imc_categorie(imc):
                if imc >= 40:
                    return "Obésité massive"
                elif imc >= 35:
                    return "Obésité sévère"
                elif imc >= 30:
                    return "Obésité modérée"
                elif imc >= 25:
                    return "Surpoids"
                else:
                    return "Normal"

            debut = imc_data.iloc[0]
            fin = imc_data.iloc[-1]
            cat_debut = imc_categorie(debut["imc"])
            cat_fin = imc_categorie(fin["imc"])
            if cat_fin != cat_debut:
                niveau = [
                    "Normal",
                    "Surpoids",
                    "Obésité modérée",
                    "Obésité sévère",
                    "Obésité massive",
                ]
                if niveau.index(cat_fin) > niveau.index(cat_debut):
                    alertes_sante.append("imc")
                    alertes_sante_details.append(
                        f"IMC est passé de {debut['imc']:.1f} ({cat_debut}) en {int(debut['année'])} à {fin['imc']:.1f} ({cat_fin}) en {int(fin['année'])}"
                    )

    # --- Tour de taille ---
    if "périmétre abdominal" in agent_data.columns and "sexe" in agent_data.columns:
        sexe_data = agent_data["sexe"].dropna()
        if not sexe_data.empty:
            sexe = sexe_data.iloc[-1].strip().lower()
            tour_data = agent_data[["année", "périmétre abdominal"]].dropna()
            tour_data = tour_data[tour_data["année"].between(2019, 2024)].sort_values(
                "année"
            )
            if len(tour_data) >= 2:
                seuil = 94 if sexe == "homme" else 80
                seuil_depasse_annee = tour_data[
                    tour_data["périmétre abdominal"] > seuil
                ]
                if not seuil_depasse_annee.empty:
                    annee_depasse = int(seuil_depasse_annee.iloc[0]["année"])
                    valeur = seuil_depasse_annee.iloc[0]["périmétre abdominal"]
                    alertes_sante.append("tour")
                    alertes_sante_details.append(
                        f"Tour de taille a dépassé {seuil} cm ({sexe}) en {annee_depasse} avec {valeur:.1f} cm"
                    )

    return alertes_sante, alertes_sante_details


@app.route("/", methods=["GET", "POST"])
def index():
    error = None

    if request.method == "POST":
        matricule = request.form.get("matricule", "").strip()
        agent_data = df[df["matricule"] == matricule]

        if agent_data.empty:
            error = f"Matricule {matricule} non trouvé."
            return render_template("index.html", error=error)

        # --- infos agent ---
        grade = agent_data["grade"].iloc[0] if "grade" in agent_data else "Inconnu"
        grade_image = f"/static/grades/{grade.lower().replace(' ', '_')}.png"
        poids = "N/A"
        for an in range(2024, 2010, -1):
            poids_annee = agent_data[agent_data["année"] == an]["poids"].dropna()
            if not poids_annee.empty:
                poids = f" {poids_annee.iloc[0]} ({an})"
                break

        taille = (
            agent_data["taille"].dropna().iloc[-1]
            if "taille" in agent_data and not agent_data["taille"].dropna().empty
            else "N/A"
        )

        localisation = agent_data["cis"].iloc[-1] if "cis" in agent_data else "N/A"
        age = (
            agent_data["age"].dropna().iloc[-1]
            if "age" in agent_data and not agent_data["age"].dropna().empty
            else "N/A"
        )

        categorie = (
            agent_data["catégorie"].iloc[-1] if "catégorie" in agent_data else "N/A"
        )
        genre = agent_data["sexe"].iloc[-1] if "sexe" in agent_data else "N/A"
        alertes_sante, alertes_sante_details = generate_alertes_sante_evolution(
            agent_data
        )

        # --- graphiques physiques ---
        charts = []
        for test, label in test_labels.items():
            if test not in agent_data.columns:
                continue
            niveau_col = niveau_cols.get(test)
            if not niveau_col or niveau_col not in agent_data.columns:
                continue

            fig, ax = plt.subplots(figsize=(6, 3.5))
            x = agent_data["année"]
            y = agent_data[test]
            niveaux = agent_data[niveau_col]

            colors = niveaux.map({1: "red", 2: "orange", 3: "green"}).fillna("gray")
            fig.patch.set_facecolor("#1a1a1a")
            ax.set_facecolor("#1a1a1a")
            scatter = ax.scatter(
                x, y, c=colors, s=100, edgecolors="white", linewidths=1.5
            )

            for i, val in enumerate(y):
                ax.annotate(
                    f"{val}",
                    (x.iloc[i], y.iloc[i]),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontsize=9,
                    color="white",
                )

            ax.set_title(f"{label}", color="white")
            ax.set_xlabel("Année", color="white")
            ax.set_ylabel("Résultat", color="white")
            ax.tick_params(colors="white")
            ax.grid(True, linestyle="--", alpha=0.3)

            from matplotlib.lines import Line2D

            legend_elements = [
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    label="Niveau 1",
                    markerfacecolor="red",
                    markersize=9,
                ),
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    label="Niveau 2",
                    markerfacecolor="orange",
                    markersize=9,
                ),
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    label="Niveau 3",
                    markerfacecolor="green",
                    markersize=9,
                ),
            ]
            ax.legend(
                handles=legend_elements,
                loc="best",
                facecolor="#2a2a2a",
                edgecolor="#444",
                labelcolor="white",
            )
            fig.tight_layout()
            charts.append((label, fig_to_base64(fig)))

        # --- Analyse des baisses ---
        baisses = []
        baisses_detaillees = []

        for test, label in test_labels.items():
            if test not in agent_data.columns:
                continue

            test_data = agent_data[["année", test]].dropna()
            if test_data.empty:
                continue

            valeurs = test_data.set_index("année")[test]
            valeurs = valeurs.loc[valeurs.index.isin(range(2019, 2025))]

            if len(valeurs) < 2:
                continue

            val_max = valeurs.max()
            an_max = valeurs.idxmax()
            val_recent = valeurs.sort_index().iloc[-1]
            an_recent = valeurs.sort_index().index[-1]

            if val_max == 0:
                continue

            baisse_pct = ((val_max - val_recent) / val_max) * 100
            baisses.append(baisse_pct)

            if baisse_pct >= 10:
                baisses_detaillees.append(
                    {
                        "test": label,
                        "pourcentage": round(baisse_pct, 1),
                        "valeur_max": val_max,
                        "annee_max": an_max,
                        "valeur_recent": val_recent,
                        "annee_recent": an_recent,
                    }
                )

        alerte = None
        if any(b >= 30 for b in baisses):
            alerte = "⚠️ Alerte : une baisse ≥ 30% a été détectée sur un test."
        elif sum(1 for b in baisses if b >= 20) >= 2:
            alerte = "⚠️ Alerte : deux tests ont baissé de ≥ 20%."
        elif sum(1 for b in baisses if b >= 10) >= 3:
            alerte = "⚠️ Alerte : trois tests ou plus ont baissé de ≥ 10%."

        # --- IMC ---
        if "imc" in agent_data.columns:
            fig_imc, ax_imc = plt.subplots(figsize=(6, 3.5))
            fig_imc.patch.set_facecolor("#1a1a1a")
            ax_imc.set_facecolor("#1a1a1a")

            imc_data = agent_data[["année", "imc"]].dropna().sort_values("année")
            if not imc_data.empty:

                def get_color_and_label(imc):
                    if imc >= 40:
                        return ("#8B0000", "Obésité massive")
                    elif imc >= 35:
                        return ("#FF4500", "Obésité sévère")
                    elif imc >= 30:
                        return ("#FFA500", "Obésité modérée")
                    elif imc >= 25:
                        return ("#FFD700", "Surpoids")
                    else:
                        return ("#32CD32", "Normal")

                years = imc_data["année"]
                values = imc_data["imc"]
                colors = [get_color_and_label(val)[0] for val in values]
                labels = [get_color_and_label(val)[1] for val in values]

                scatter = ax_imc.scatter(
                    years,
                    values,
                    c=colors,
                    s=100,
                    edgecolors="white",
                    linewidths=1.5,
                )

                # Annotations des valeurs
                for i, val in enumerate(values):
                    ax_imc.annotate(
                        f"{val:.1f}",
                        (years.iloc[i], val),
                        textcoords="offset points",
                        xytext=(0, 6),
                        ha="center",
                        fontsize=9,
                        color="white",
                    )

                # Légende personnalisée
                from matplotlib.lines import Line2D

                legend_elements = [
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Normal",
                        markerfacecolor="#32CD32",
                        markersize=9,
                    ),
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Surpoids",
                        markerfacecolor="#FFD700",
                        markersize=9,
                    ),
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Obésité modérée",
                        markerfacecolor="#FFA500",
                        markersize=9,
                    ),
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Obésité sévère",
                        markerfacecolor="#FF4500",
                        markersize=9,
                    ),
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Obésité massive",
                        markerfacecolor="#8B0000",
                        markersize=9,
                    ),
                ]
                ax_imc.legend(
                    handles=legend_elements,
                    loc="best",
                    facecolor="#2a2a2a",
                    edgecolor="#444",
                    labelcolor="white",
                )

                ax_imc.set_title("Évolution de l'IMC", color="white")
                ax_imc.set_xlabel("Année", color="white")
                ax_imc.set_ylabel("IMC", color="white")
                ax_imc.tick_params(colors="white")
                ax_imc.grid(True, linestyle="--", alpha=0.3)
                fig_imc.tight_layout()
                imc_chart = fig_to_base64(fig_imc)
        else:
            imc_chart = None

        # --- Périmètre abdominal ---
        if "périmétre abdominal" in agent_data.columns and "sexe" in agent_data.columns:
            fig_tour, ax_tour = plt.subplots(figsize=(6, 3.5))
            fig_tour.patch.set_facecolor("#1a1a1a")
            ax_tour.set_facecolor("#1a1a1a")

            tour_data = (
                agent_data[["année", "périmétre abdominal"]]
                .dropna()
                .sort_values("année")
            )
            if not tour_data.empty:
                sexe_data = agent_data["sexe"].dropna()
                sexe = (
                    sexe_data.iloc[-1].strip().lower()
                    if not sexe_data.empty
                    else "inconnu"
                )
                seuil = 94 if sexe == "homme" else 80

                years = tour_data["année"]
                values = tour_data["périmétre abdominal"]
                colors = ["red" if val > seuil else "green" for val in values]

                scatter = ax_tour.scatter(
                    years,
                    values,
                    c=colors,
                    s=100,
                    edgecolors="white",
                    linewidths=1.5,
                )

                for i, val in enumerate(values):
                    ax_tour.annotate(
                        f"{val:.1f}",
                        (years.iloc[i], val),
                        textcoords="offset points",
                        xytext=(0, 6),
                        ha="center",
                        fontsize=9,
                        color="white",
                    )

                from matplotlib.lines import Line2D

                legend_elements = [
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label="Normal",
                        markerfacecolor="green",
                        markersize=9,
                    ),
                    Line2D(
                        [0],
                        [0],
                        marker="o",
                        color="w",
                        label=f"Dépassé ({seuil} cm)",
                        markerfacecolor="red",
                        markersize=9,
                    ),
                ]
                ax_tour.legend(
                    handles=legend_elements,
                    loc="best",
                    facecolor="#2a2a2a",
                    edgecolor="#444",
                    labelcolor="white",
                )

                ax_tour.set_title("Tour de Taille", color="white")
                ax_tour.set_xlabel("Année", color="white")
                ax_tour.set_ylabel("cm", color="white")
                ax_tour.tick_params(colors="white")
                ax_tour.grid(True, linestyle="--", alpha=0.3)
                fig_tour.tight_layout()
                tour_chart = fig_to_base64(fig_tour)
        else:
            tour_chart = None

        return render_template(
            "agent.html",
            matricule=matricule,
            grade=grade,
            grade_image=grade_image,
            poids=poids,
            taille=taille,
            localisation=localisation,
            age=age,
            categorie=categorie,
            genre=genre,
            charts=charts,
            imc_chart=imc_chart,
            tour_chart=tour_chart,
            alerte=alerte,
            baisses_detaillees=baisses_detaillees,
            alertes_sante=alertes_sante,
            alertes_sante_details=alertes_sante_details,
        )

    return render_template("index.html", error=error)


# Ajoute ceci dans app.py

from flask import jsonify


@app.route("/alertes")
def alertes():
    alertes_liste = []
    matricules = df["matricule"].unique()

    for mat in matricules:
        agent_data = df[df["matricule"] == mat]
        alertes_sante, _ = generate_alertes_sante_evolution(agent_data)

        # Analyse tests physiques
        baisses = []
        for test in test_labels:
            if test not in agent_data.columns:
                continue
            test_data = agent_data[["année", test]].dropna()
            if test_data.empty:
                continue
            valeurs = test_data.set_index("année")[test]
            valeurs = valeurs.loc[valeurs.index.isin(range(2019, 2025))]
            if len(valeurs) < 2:
                continue
            val_max = valeurs.max()
            val_recent = valeurs.sort_index().iloc[-1]
            if val_max == 0:
                continue
            baisse_pct = ((val_max - val_recent) / val_max) * 100
            baisses.append(baisse_pct)

        types = []
        if alertes_sante:
            types.append("Santé")
        if (
            any(b >= 30 for b in baisses)
            or sum(1 for b in baisses if b >= 20) >= 2
            or sum(1 for b in baisses if b >= 10) >= 3
        ):
            types.append("Tests physiques")

        if types:
            alertes_liste.append(
                {"matricule": mat, "nombre": len(types), "types": ", ".join(types)}
            )

    return render_template("alertes.html", alertes=alertes_liste)


if __name__ == "__main__":
    app.run(debug=True)
