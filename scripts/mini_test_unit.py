"""
LYRA GENESIS - MINI TEST UNIT
=============================
Test rapide de la logique de vectorisation et de normalisation
sur un échantillon réduit avant le déploiement massif.
"""
import requests
import numpy as np
from pathlib import Path
from tqdm import tqdm
import sys

# --- CONFIG ---
# On prend un échantillon représentatif (Hétérogène pour tester le filtrage)
SAMPLE_CONCEPTS = [
    # Groupe A : Philosophie (Doivent matcher entre eux)
    "Hegel", "Dialectique", "Phénoménologie", "Esprit Absolu", "Aufhebung",
    "Spinoza", "Substance", "Conatus", "Éthique", "Dieu",
    
    # Groupe B : Physique (Doivent matcher entre eux, moins avec A)
    "Mécanique Quantique", "Fonction d'onde", "Photon", "Intrication", "Heisenberg",
    "Entropie", "Thermodynamique", "Chaos", "Attracteur", "Énergie",
    
    # Groupe C : Bruit / Contrôle (Ne doivent matcher avec rien ou peu)
    "Banane", "Recette de crêpes", "Camion", "Tournevis", "Chaussette"
]

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mxbai-embed-large"
SIMILARITY_THRESHOLD = 0.70

def run_test():
    print(f"🧪 Démarrage du MINI-TEST sur {len(SAMPLE_CONCEPTS)} concepts...")
    
    # 1. VECTORISATION
    embeddings = []
    valid_concepts = []
    
    print("   📡 Vectorisation via Ollama...")
    for concept in tqdm(SAMPLE_CONCEPTS):
        try:
            resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": concept})
            if resp.status_code == 200:
                vec = resp.json().get("embedding")
                if vec:
                    embeddings.append(vec)
                    valid_concepts.append(concept)
        except Exception as e:
            print(f"   ❌ Erreur connexion: {e}")
            return

    # 2. CALCUL MATHÉMATIQUE (Le coeur du test)
    print("   📐 Calcul Matriciel (float32 + Normalisation L2)...")
    
    # --- LA LOGIQUE CORRIGÉE ---
    emb_array = np.array(embeddings, dtype=np.float32)
    
    # Norme L2
    norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0 # Sécurité
    
    # Normalisation
    normalized = emb_array / norms
    
    # Similarité Cosinus
    similarity_matrix = np.dot(normalized, normalized.T)
    # ---------------------------

    # 3. ANALYSE DES RÉSULTATS
    print("\n📊 ANALYSE FORENSIQUE DES POIDS :")
    
    weights = []
    edges_count = 0
    
    # On parcourt la matrice
    rows, cols = np.where(similarity_matrix > SIMILARITY_THRESHOLD)
    
    # Pour l'affichage de quelques exemples
    examples_good = []
    examples_bad = []
    
    for i, j in zip(rows, cols):
        if i >= j: continue # On ne regarde qu'une fois chaque paire, pas de self-loop
        
        w = float(similarity_matrix[i, j])
        weights.append(w)
        edges_count += 1
        
        pair = f"{valid_concepts[i]} <-> {valid_concepts[j]}"
        
        # Capture d'exemples
        if w > 0.85 and len(examples_good) < 3:
            examples_good.append(f"  ✅ LIEN FORT  ({w:.4f}) : {pair}")
        if w < 0.72 and w > SIMILARITY_THRESHOLD and len(examples_bad) < 3:
            examples_bad.append(f"  ⚠️ LIEN LIMITE ({w:.4f}) : {pair}")

    if not weights:
        print("❌ AUCUN LIEN TROUVÉ ! Le seuil est peut-être trop haut ou la normalisation a échoué.")
        return

    min_w = min(weights)
    max_w = max(weights)
    avg_w = sum(weights) / len(weights)
    
    print(f"   - Poids Min   : {min_w:.4f}")
    print(f"   - Poids Max   : {max_w:.4f} (Doit être <= 1.0)")
    print(f"   - Poids Moy   : {avg_w:.4f} (Cible: 0.75 - 0.85)")
    print(f"   - Densité     : {edges_count} liens pour {len(valid_concepts)} concepts")
    
    print("\n🔍 EXEMPLES DE CONNEXIONS :")
    for ex in examples_good: print(ex)
    for ex in examples_bad: print(ex)
    
    # Vérification des intrus
    print("\n🕵️ TEST DE COHÉRENCE (Le Test de la Banane) :")
    banane_idx = -1
    if "Banane" in valid_concepts:
        banane_idx = valid_concepts.index("Banane")
        # Chercher les liens de la banane
        banane_links = []
        for j in range(len(valid_concepts)):
            if j == banane_idx: continue
            w = similarity_matrix[banane_idx, j]
            if w > SIMILARITY_THRESHOLD:
                banane_links.append(f"{valid_concepts[j]} ({w:.2f})")
        
        if not banane_links:
            print("   ✅ SUCCÈS : 'Banane' est isolée (0 connexion). Le filtre fonctionne.")
        else:
            print(f"   ❌ ÉCHEC : 'Banane' est connectée à : {', '.join(banane_links)}")
    
    if max_w > 1.01:
        print("\n🚨 ALERTE : La normalisation a échoué (Poids > 1.0).")
    else:
        print("\n✨ CONCLUSION : La logique mathématique est VALIDE. Vous pouvez lancer le gros script.")

if __name__ == "__main__":
    run_test()