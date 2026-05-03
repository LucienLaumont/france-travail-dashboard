import os
import re
from datetime import datetime, timezone

from france_travail import FranceTravailClient, SearchParams
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
FT_CLIENT_ID = os.environ["FT_CLIENT_ID"]
FT_CLIENT_SECRET = os.environ["FT_CLIENT_SECRET"]

MOTS_CLES = [
    "Data Scientist",
    "Data Analyst",
    "Machine Learning Engineer",
    "AI Engineer",
]

PUBLIEE_DEPUIS = 31  # jours


_SALAIRE_RE = re.compile(
    r"(Annuel|Mensuel|Horaire) de ([\d.]+) Euros à ([\d.]+) Euros(?: sur ([\d.]+) mois)?"
)


def parse_salaire(libelle):
    if not libelle:
        return None, None
    m = _SALAIRE_RE.search(libelle)
    if not m:
        return None, None
    periode, raw_min, raw_max, nb_mois = m.groups()
    sal_min, sal_max = float(raw_min), float(raw_max)
    if periode == "Mensuel":
        nb_mois = float(nb_mois) if nb_mois else 12.0
        sal_min *= nb_mois
        sal_max *= nb_mois
    elif periode == "Horaire":
        return None, None  # pas assez d'info pour annualiser
    return round(sal_min, 2), round(sal_max, 2)


def _str(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def extract_offre(offre):
    lieu = getattr(offre, "lieuTravail", None) or getattr(offre, "lieu_travail", None)
    entreprise = getattr(offre, "entreprise", None)
    salaire = getattr(offre, "salaire", None)
    date_creation = getattr(offre, "dateCreation", None) or getattr(offre, "date_creation", None)
    is_alternance = getattr(offre, "alternance", None)
    salaire_libelle = getattr(salaire, "libelle", None) if salaire else None
    salaire_min, salaire_max = parse_salaire(salaire_libelle)

    return {
        "id": offre.id,
        "intitule": offre.intitule,
        "description": getattr(offre, "description", None),
        "type_contrat": getattr(offre, "typeContrat", None) or getattr(offre, "type_contrat", None),
        "lieu_travail": getattr(lieu, "libelle", None) if lieu else None,
        "entreprise_nom": getattr(entreprise, "nom", None) if entreprise else None,
        "entreprise_description": getattr(entreprise, "description", None) if entreprise else None,
        "rome_code": getattr(offre, "romeCode", None) or getattr(offre, "rome_code", None),
        "rome_libelle": getattr(offre, "romeLibelle", None) or getattr(offre, "rome_libelle", None),
        "is_alternance" : is_alternance,
        "salaire_libelle": salaire_libelle,
        "salaire_min": salaire_min,
        "salaire_max": salaire_max,
        "date_creation": _str(date_creation),
        "date_collecte": datetime.now(timezone.utc).isoformat(),
    }


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    all_rows = {}

    with FranceTravailClient(client_id=FT_CLIENT_ID, client_secret=FT_CLIENT_SECRET) as client:
        for mot in MOTS_CLES:
            result = client.search(SearchParams(
                motsCles=mot,
                publieeDepuis=PUBLIEE_DEPUIS,
                range_="0-149",
            ))
            offres = getattr(result, "resultats", []) or []
            for o in offres:
                all_rows[o.id] = extract_offre(o)
            print(f"  {mot} : {len(offres)} offres")

    if not all_rows:
        print("Aucune offre trouvée.")
        return

    rows = list(all_rows.values())
    supabase.table("offres").upsert(rows, on_conflict="id").execute()
    print(f"{len(rows)} offres insérées/mises à jour (doublons inter-mots-clés dédupliqués).")


if __name__ == "__main__":
    main()
