# France Travail Dashboard

Dashboard de veille automatisé sur les offres d'emploi **Data / IA** en France. Les offres sont collectées chaque jour via l'API France Travail et affichées dans une interface statique hébergée sur GitHub Pages.

**Live** → [lucienlaumont.github.io/france-travail-dashboard](https://LucienLaumont.github.io/france-travail-dashboard/)

---

## Ce que le dashboard affiche

| Bloc | Description |
|---|---|
| **KPIs** | Nombre total d'offres, entreprises uniques, salaire moyen annualisé, nombre de localisations |
| **Offres par jour** | Courbe Chart.js du volume collecté chaque jour |
| **Répartition contrats** | Donut Chart.js (CDI / CDD / MIS / etc.) |
| **Top entreprises** | Tableau classé avec barres proportionnelles |
| **Top localisations** | Tableau classé avec barres proportionnelles |
| **Liste des offres** | Titre, entreprise, lieu, type de contrat, fourchette salariale, lien direct vers France Travail — paginée par 15, filtrable par texte et type de contrat |

---

## Architecture

```
GitHub Actions (cron 18h UTC+1)
    │
    ├── pip install france-travail-job-offers
    └── scripts/collect.py
            │
            └── Supabase (PostgreSQL)
                    │
                    └── docs/index.html  ←  fetch() public (clé anon)
                            │
                            └── GitHub Pages
```

---

## Stack technique

| Composant | Technologie |
|---|---|
| Collecte automatique | GitHub Actions (cron quotidien) |
| SDK offres | [`france-travail-job-offers`](https://pypi.org/project/france-travail-job-offers/) |
| Base de données | Supabase (PostgreSQL — free tier) |
| Dashboard | HTML + JS vanilla + [Chart.js](https://www.chartjs.org/) via CDN |
| Hébergement | GitHub Pages (branche `main`, dossier `/docs`) |

---

## Structure du repo

```
france-travail-dashboard/
├── .github/
│   └── workflows/
│       └── collect.yml      # cron 18h → collecte → upsert Supabase
├── docs/
│   ├── index.html           # dashboard HTML/JS vanilla
│   ├── colors_and_type.css  # design system Mistral-Warm
│   └── assets/
│       ├── favicon.svg
│       └── logo-block.svg
├── scripts/
│   └── collect.py           # script de collecte Python
├── requirements.txt
└── README.md
```

---

## Table Supabase — `offres`

| Colonne | Type | Description |
|---|---|---|
| `id` | TEXT (PK) | Identifiant unique France Travail — clé de déduplication |
| `intitule` | TEXT | Intitulé du poste |
| `type_contrat` | TEXT | CDI, CDD, MIS, LIB… |
| `lieu_travail` | TEXT | Libellé de la localisation |
| `entreprise_nom` | TEXT | Nom de l'entreprise |
| `rome_code` | TEXT | Code ROME |
| `rome_libelle` | TEXT | Libellé ROME |
| `salaire_libelle` | TEXT | Libellé brut de l'API |
| `salaire_min` | NUMERIC | Salaire annualisé minimum (parsé) |
| `salaire_max` | NUMERIC | Salaire annualisé maximum (parsé) |
| `date_creation` | TIMESTAMPTZ | Date de publication de l'offre |
| `date_collecte` | TIMESTAMPTZ | Date d'insertion en base |

Les salaires mensuels sont automatiquement convertis en annuel (`× nb_mois`, 12 par défaut). Les salaires horaires sont ignorés (non annualisables).

---

## Collecte

Le script [`scripts/collect.py`](scripts/collect.py) :

- Recherche plusieurs mots-clés en parallèle (`Data Scientist`, `Data Analyst`, `Machine Learning Engineer`, `AI Engineer`)
- Filtre sur `publieeDepuis = 1` jour pour ne récupérer que les nouvelles offres
- Déduplique les offres inter-mots-clés avant insertion
- Fait un **upsert** sur `id` — pas de doublons entre deux runs

Le workflow [`collect.yml`](.github/workflows/collect.yml) tourne à **17h UTC (≈ 18h heure de Paris)**, déclenchable manuellement via `workflow_dispatch`.

---

## Variables et secrets

### GitHub Actions secrets

| Secret | Valeur |
|---|---|
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_KEY` | Clé `service_role` (accès en écriture) |
| `FT_CLIENT_ID` | Client ID de l'API France Travail |
| `FT_CLIENT_SECRET` | Client Secret de l'API France Travail |

---

## Déploiement

1. Créer la table `offres` dans Supabase (SQL Editor)
2. Activer le RLS : `ALTER TABLE offres ENABLE ROW LEVEL SECURITY;`
3. Ajouter les 4 secrets dans les settings du repo GitHub
4. Remplacer `SUPABASE_URL` et `SUPABASE_ANON_KEY` dans `docs/index.html`
5. Activer GitHub Pages : Settings → Pages → Branch `main` → Folder `/docs`
6. Pousser sur `main` — le dashboard est live, le cron tourne chaque soir

--

Projet mis en place par **Lucien Laumont**(https://lucienlaumont.github.io/france-travail-dashboard/)