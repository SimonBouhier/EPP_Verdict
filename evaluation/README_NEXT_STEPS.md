#!/usr/bin/env python3
"""
README_NEXT_STEPS.md - Instructions pour Phase 2 (Option B Full - 60 Responses)

Le pilot est complété avec succès. Voici comment procéder à l'évaluation complète.
"""

# ============================================================================
# ÉTAPE 1 : CONFIGURER ANTHROPIC API
# ============================================================================

"""
Dans PowerShell, avant de lancer les scripts:

$env:ANTHROPIC_API_KEY = 'sk-ant-YOUR_KEY_HERE'

Vérifier:
$env:ANTHROPIC_API_KEY   # Ne doit PAS être vide

Note: Cette clé est temporaire pour la session. Elle ne sera perdue à la fermeture.
Pour persistance permanente, ajouter à $PROFILE ou utiliser variables système.
"""

# ============================================================================
# ÉTAPE 2 : ADAPTER generate_full_60_responses.py
# ============================================================================

"""
Créer nouveau script pour générer 60 réponses réelles (pas du mock):

4 Configurations:
  • baseline          (Raw Ollama, defaults)
  • temp_only         (Lyra temperature mapping, no system prompt)
  • system_only       (Lyra system prompt, default temperature)
  • full_lyra         (Full Lyra orchestration)

15 Prompts Stratifiés:
  • 5 Technical       (factual, factual knowledge)
  • 5 Creative        (open-ended, imagination)
  • 5 Analytical      (reasoning, comparison)

Total: 4 configs × 15 prompts = 60 responses

Script Requis:
  1. Connect to Ollama (http://localhost:11434)
  2. For each config × prompt pair:
     a. Call /chat/message or /generate endpoint
     b. Record response + latency
     c. Save to evaluation/1_source_data/responses_full_60.jsonl
  3. Format JSONL:
     {
       "config_id": "baseline|temp_only|system_only|full_lyra",
       "prompt": "...",
       "domain": "technical|creative|analytical",
       "response": "...",
       "latency_ms": 1234.5,
       "timestamp": "ISO8601"
     }
"""

# ============================================================================
# ÉTAPE 3 : EXÉCUTER PIPELINE COMPLET
# ============================================================================

"""
Une fois responses_full_60.jsonl créé:

# (Optionnel) Sauvegarder données précédentes
mv evaluation/1_source_data/pilot_data.jsonl evaluation/1_source_data/pilot_data_backup.jsonl
mv evaluation/1_source_data/mapping_secret.json evaluation/1_source_data/mapping_secret_backup.json

# Renouveler les dossiers
rm evaluation/2_blind_data/*
rm evaluation/3_judgments/*
rm evaluation/4_results/*

# Lancer nouveau pipeline
python C:\Users\simon\PROJECTS\lyra_clean\.venv\Scripts\python.exe evaluation/scripts/1_anonymize.py
python C:\Users\simon\PROJECTS\lyra_clean\.venv\Scripts\python.exe evaluation/scripts/2_judge.py     # REAL API (pas demo)
python C:\Users\simon\PROJECTS\lyra_clean\.venv\Scripts\python.exe evaluation/scripts/3_unblind.py
python C:\Users\simon\PROJECTS\lyra_clean\.venv\Scripts\python.exe evaluation/scripts/4_analyze_full.py
"""

# ============================================================================
# ÉTAPE 4 : CRÉER 4_analyze_full.py AVEC STATS COMPLÈTES
# ============================================================================

"""
Améliorations par rapport à 4_analyze_pilot.py:

1. T-Tests Entre Configs
   • H0: Config A = Config B
   • Comparer chaque paire (6 comparaisons)
   • Bonferroni correction pour multiple testing
   • Report p-values et significance

2. Effect Sizes (Cohen's d)
   • Mesurer magnitude des différences
   • Interpréter: negligible < 0.2, small < 0.5, medium < 0.8, large
   • Visualiser avec barcharts

3. Confidence Intervals (95%)
   • Pour chaque config: mean ± 1.96*SE
   • Overlaps = not significant
   • Separation = likely significant

4. Domaine-Spécifique Breakdown
   • Scores par domain (technical, creative, analytical)
   • Lyra meilleur pour creative?
   • Raw meilleur pour technical?

5. Visualisations
   • Boxplots par config
   • Dotplots avec means
   • Heatmap: configs × domains

Output Format:
  ├─ analysis_summary.txt         (texte brut, easy read)
  ├─ analysis_full.json           (données complètes)
  ├─ config_comparison.png        (boxplot)
  ├─ domain_breakdown.png         (faceted plot)
  └─ analysis_report.md           (markdown complet)
"""

# ============================================================================
# ÉTAPE 5 : GO/NO-GO DECISION LOGIC
# ============================================================================

"""
Basé sur résultats Option B (60 responses), décider:

🟢 GO FORWARD (Option A - Full Evaluation, 750 responses):
  ✓ Au moins une différence p < 0.05 entre configs
  ✓ Effect size Cohen's d > 0.3 pour au moins un component
  ✓ Résultats cohérents entre domaines (pas inversions)
  ✓ Judge reliability satisfactory (ou calibration possible)

  Prochaine action:
    → Full Option A avec calibration
    → 250 prompts test × 3 configs = 750 responses
    → Appliquer Rogan & Gladen bias correction
    → Budget: ~$7-15 USD, 1 week

🔴 NO-GO (Pivot Strategy):
  ✗ Aucune différence significative (tous p > 0.2)
  ✗ Tous effect sizes < 0.2 (negligible)
  ✗ Résultats incohérents (inversions par domain)
  ✗ Judge unreliable et pas moyen de calibrer

  Prochaine action:
    → Passer à human evaluation (Mechanical Turk)
    → Ou repositionner Lyra comme "orchestration framework"
    → Ou investiguer ablation study (temp vs system vs penalties)

⚠️  MARGINAL CASE (Need More Data):
  ? Quelques différences (p < 0.10) mais pas p < 0.05
  ? Effect sizes petits (0.2 < d < 0.3)
  ? Résultats prometteurs mais pas conclusifs

  Prochaine action:
    → Augmenter n (90-100 prompts)
    → Ou refiner categories de prompts
    → Ou investiguer ablation study
"""

# ============================================================================
# ÉTAPE 6 : OPTIONAL - ABLATION STUDY
# ============================================================================

"""
Si Option B montre différence mais cause incertain:

Isoler composantes de Lyra:

Config 1: baseline (raw)
Config 2: temp_only (just temperature change)
Config 3: system_only (just system prompt)
Config 4: temp+system (both)
Config 5: full_lyra (complete orchestration)

Compare effet de chaque composante:
  • Temperature seule: Config 2 - Config 1
  • System prompt seule: Config 3 - Config 1
  • Combinaison: Config 4 - Config 1 vs additif?
  • Lyra complet: Config 5 - Config 1

Voir ABLATION_STUDY_PLAN.md pour détails.
"""

# ============================================================================
# TIMELINE ESTIMÉE
# ============================================================================

"""
Option B Full (60 responses):
  • Jour 1 Matin (1-2h) : Generate 60 responses
  • Jour 1 Après (2-3h) : Anonymize + Judge Claude + Unblind
  • Jour 1 Fin (30min) : Analyze
  • Jour 2 Matin : Review & Decision

Total: 1-1.5 jours
Budget API: ~$0.50 USD
"""

# ============================================================================
# CHECKLIST AVANT DE LANCER
# ============================================================================

CHECKLIST = """
ANTES DE LANCER OPTION B FULL:

Infrastructure:
  [ ] Ollama running (http://localhost:11434)
  [ ] Lyra server accessible (http://localhost:8000)
  [ ] ANTHROPIC_API_KEY configuré en PowerShell
  
Code:
  [ ] generate_full_60_responses.py créé et testé
  [ ] evaluation/1_source_data/responses_full_60.jsonl générée
  [ ] 4_analyze_full.py créé avec stats complètes
  
Data:
  [ ] Pilot résultats sauvegardés (backup)
  [ ] Nouveau dossier evaluation/ prêt pour Option B
  [ ] Mapping secret n'est pas partagé
  
Documentation:
  [ ] Ce fichier README_NEXT_STEPS.md lu
  [ ] OPTION_B_EXECUTION_PLAN.md révisé
  [ ] Budget API approuvé

Prêt à lancer:
  [ ] python evaluation/scripts/1_anonymize.py
  [ ] python evaluation/scripts/2_judge.py         # REAL API
  [ ] python evaluation/scripts/3_unblind.py
  [ ] python evaluation/scripts/4_analyze_full.py
"""

if __name__ == "__main__":
    print(CHECKLIST)
