from flask import Flask, render_template, request
import pandas as pd
import os
import matplotlib

matplotlib.use("Agg")  # Utilise un backend sans interface graphique

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


# Fonction pour tracer les courbes et les convertir en base64
def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


@app.route("/", methods=["GET", "POST"])
def index():
    agent_data = None
    error = None
    test_labels = {
        "resul gain": "Gainage",
        "resul killy": "Killy",
        "resul ll": "Luc Léger",
        "resul pompes": "Pompes",
        "resul souplesse": "Souplesse",
        "resul tractions": "Tractions",
    }

    if request.method == "POST":
        matricule = request.form.get("matricule", "").strip()
        selected_tests = request.form.getlist("tests")

        # Si aucun test n'est coché, on garde tous par défaut
        if not selected_tests:
            selected_tests = list(test_labels.keys())

        agent_data = df[df["matricule"] == matricule]

        if agent_data.empty:
            error = f"Matricule {matricule} non trouvé."
            return render_template("index.html", error=error)

        grade = (
            agent_data["grade"].iloc[0] if "grade" in agent_data.columns else "Inconnu"
        )
        grade_image = f"/static/grades/{grade.lower().replace(' ', '_')}.png"

        # Courbe des tests physiques
        tests_time = agent_data.groupby("année")[selected_tests].mean()
        fig1, ax1 = plt.subplots(figsize=(10, 5))
        for col in tests_time.columns:
            if pd.api.types.is_numeric_dtype(tests_time[col]):
                ax1.plot(
                    tests_time.index,
                    tests_time[col],
                    marker="o",
                    label=test_labels[col],
                )
        ax1.set_title("Évolution des tests physiques")
        ax1.set_xlabel("Année")
        ax1.set_ylabel("Résultat")
        ax1.legend()
        test_chart = fig_to_base64(fig1)

        # IMC
        if "imc" in agent_data.columns:
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            imc_time = agent_data.groupby("année")["imc"].mean()
            ax2.plot(imc_time.index, imc_time.values, marker="o", color="purple")
            ax2.set_title("Évolution de l'IMC")
            ax2.set_xlabel("Année")
            ax2.set_ylabel("IMC")
            imc_chart = fig_to_base64(fig2)
        else:
            imc_chart = None
        # Infos supplémentaires
        poids = agent_data["poids"].iloc[-1] if "poids" in agent_data.columns else "N/A"
        taille = (
            agent_data["taille"].iloc[-1] if "taille" in agent_data.columns else "N/A"
        )
        localisation = (
            agent_data["cis"].iloc[-1]
            if "cis" in agent_data.columns
            else "Non renseignée"
        )
        age = (
            agent_data["age"].iloc[-1]
            if "age" in agent_data.columns
            else "Non renseignée"
        )
        categorie = (
            agent_data["catégorie"].iloc[-1]
            if "catégorie" in agent_data.columns
            else "Non renseignée"
        )

        return render_template(
            "agent.html",
            matricule=matricule,
            grade=grade,
            grade_image=grade_image,
            test_chart=test_chart,
            imc_chart=imc_chart,
            test_labels=test_labels,
            selected_tests=selected_tests,
            poids=poids,
            taille=taille,
            localisation=localisation,
            age=age,
            categorie=categorie,
        )

    return render_template("index.html", error=error)


if __name__ == "__main__":
    app.run(debug=True)
