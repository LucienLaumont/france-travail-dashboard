import json
import os
import anthropic
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BATCH_SIZE = 40 
MODEL = "claude-haiku-4-5-20251001"

PRICE_INPUT_PER_MTOK  = 1.00
PRICE_OUTPUT_PER_MTOK = 5.00

# MISE À JOUR DU SYSTEM PROMPT
SYSTEM = """\
Tu analyses des offres d'emploi françaises. Pour chaque offre du tableau JSON fourni, détermine :

- experience_level :
  "junior"  → 0-2 ans, ou mots-clés : débutant, première expérience, stage, alternance, junior
  "mid"     → 2-5 ans, ou mots-clés : confirmé, expérimenté, autonome, 3 ans, 4 ans
  "senior"  → 5+ ans, ou mots-clés : senior, expert, lead, référent, architecte, management
  "unknown" → aucun indicateur clair

- entreprise_nom : extraire le nom si "entreprise_nom" est vide. \
Regarde en priorité dans "description" et "entreprise_description". \
Si le nom est explicitement écrit, extrais-le ; sinon null. Ne jamais inventer.

Réponds UNIQUEMENT avec un tableau JSON valide dans le même ordre que l'input :
[{"id": "...", "experience_level": "...", "entreprise_nom": "..." ou null}, ...]"""


def enrich_batch(ac: anthropic.Anthropic, offres: list[dict]) -> tuple[list[dict], int, int]:
    items = [
        {
            "id": o["id"],
            "intitule": o["intitule"],
            # On passe aussi la description de l'entreprise au LLM
            "description": (o.get("description") or "")[:800],
            "entreprise_description": (o.get("entreprise_description") or "")[:400], 
            "entreprise_nom": o.get("entreprise_nom"),
        }
        for o in offres
    ]
    resp = ac.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(items, ensure_ascii=False)}],
    )
    text = resp.content[0].text
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"Réponse sans tableau JSON : {text[:200]}")
    return json.loads(text[start:end]), resp.usage.input_tokens, resp.usage.output_tokens


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    ac = anthropic.Anthropic()

    # MISE À JOUR DE LA SÉLECTION (ajout de entreprise_description)
    res = (
        supabase.table("offres")
        .select("id, intitule, description, entreprise_nom, entreprise_description")
        .eq("enriched", False)
        .limit(2000)
        .execute()
    )
    offres = [o for o in res.data if o.get("description")]

    if not offres:
        print("Aucune offre à enrichir.")
        return

    print(f"{len(offres)} offres à enrichir…")
    total = 0
    total_input  = 0
    total_output = 0

    for i in range(0, len(offres), BATCH_SIZE):
        batch = offres[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        try:
            results, in_tok, out_tok = enrich_batch(ac, batch)
            total_input  += in_tok
            total_output += out_tok
        except Exception as e:
            print(f"   Batch {batch_num} erreur : {e}")
            supabase.table("offres").upsert(
                [{"id": o["id"], "experience_level": "unknown", "enriched": True} for o in batch],
                on_conflict="id",
            ).execute()
            continue

        orig_map = {o["id"]: o for o in batch}
        upsert_rows = []
        for item in results:
            orig = orig_map.get(item.get("id"))
            if not orig:
                continue
            
            llm_nom = item.get("entreprise_nom")
            if llm_nom and llm_nom.lower() in ("null", "none", "unknown", "inconnu", "n/a", ""):
                llm_nom = None
            
            # Priorité au nom déjà présent en DB, sinon celui trouvé par le LLM
            final_nom = orig.get("entreprise_nom") or llm_nom

            upsert_rows.append({
                "id": item["id"],
                "experience_level": item.get("experience_level") or "unknown",
                "entreprise_nom": final_nom,
                "enriched": True,
            })

        if upsert_rows:
            supabase.table("offres").upsert(upsert_rows, on_conflict="id").execute()
        total += len(upsert_rows)
        print(f"   Batch {batch_num} : {len(upsert_rows)} offres enrichies")

    cost_usd = (
        total_input  / 1_000_000 * PRICE_INPUT_PER_MTOK
        + total_output / 1_000_000 * PRICE_OUTPUT_PER_MTOK
    )
    supabase.table("enrichment_runs").insert({
        "model": MODEL,
        "offers_processed": total,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": round(cost_usd, 6),
    }).execute()

    print(f"Total : {total} offres enrichies.")
    print(f"Coût estimé : ${cost_usd:.4f} ({total_input:,} tokens in, {total_output:,} tokens out)")


if __name__ == "__main__":
    main()
