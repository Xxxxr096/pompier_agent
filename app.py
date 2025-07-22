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
        poids = agent_data["poids"].iloc[-1] if "poids" in agent_data else "N/A"
        taille = agent_data["taille"].iloc[-1] if "taille" in agent_data else "N/A"
        localisation = agent_data["cis"].iloc[-1] if "cis" in agent_data else "N/A"
        age = agent_data["age"].iloc[-1] if "age" in agent_data else "N/A"
        categorie = (
            agent_data["catégorie"].iloc[-1] if "catégorie" in agent_data else "N/A"
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
        # --- IMC ---
        if "imc" in agent_data.columns:
            fig_imc, ax_imc = plt.subplots(figsize=(6, 3.5))
            fig_imc.patch.set_facecolor("#1a1a1a")
            ax_imc.set_facecolor("#1a1a1a")
            imc_time = agent_data.groupby("année")["imc"].mean()
            ax_imc.scatter(
                imc_time.index,
                imc_time.values,
                color="purple",
                s=100,
                edgecolors="white",
                linewidths=1.5,
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
        if "périmétre abdominal" in agent_data.columns:
            fig_tour, ax_tour = plt.subplots(figsize=(6, 3.5))
            fig_tour.patch.set_facecolor("#1a1a1a")
            ax_tour.set_facecolor("#1a1a1a")
            ax_tour.set_title("Tour de Taille", color="white")
            ax_tour.set_xlabel("Année", color="white")
            ax_tour.set_ylabel("cm", color="white")
            ax_tour.tick_params(colors="white")
            ax_tour.grid(True, linestyle="--", alpha=0.3)

            tour_data = agent_data.groupby("année")["périmétre abdominal"].mean()
            ax_tour.scatter(
                tour_data.index,
                tour_data.values,
                color="skyblue",
                s=100,
                edgecolors="white",
                linewidths=1.5,
            )

            ax_tour.set_title("Tour de Taille")
            ax_tour.set_xlabel("Année")
            ax_tour.set_ylabel("cm")
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
            charts=charts,
            imc_chart=imc_chart,
            tour_chart=tour_chart,
            alerte=alerte,
            baisses_detaillees=baisses_detaillees,
        )

    return render_template("index.html", error=error)


if __name__ == "__main__":
    app.run(debug=True)
