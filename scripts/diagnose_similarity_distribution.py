"""
DIAGNOSTIC - Analyser la distribution des similarités sur les 1728 concepts
"""
import sqlite3
import numpy as np
from pathlib import Path
from tqdm import tqdm

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ispace.db"

def diagnose():
    if not DB_PATH.exists():
        print(f"❌ Base de données non trouvée : {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Récupérer les statistiques des arêtes
    c.execute("SELECT weight FROM edges")
    weights = [float(row[0]) for row in c.fetchall()]
    
    if not weights:
        print("❌ Aucune arête trouvée dans la base.")
        return
    
    weights = np.array(weights)
    
    print("\n📊 DIAGNOSTIC DE DISTRIBUTION DES SIMILARITÉS\n")
    print(f"Total d'arêtes : {len(weights)}")
    print(f"Poids Min : {weights.min():.4f}")
    print(f"Poids Max : {weights.max():.4f}")
    print(f"Poids Moyen : {weights.mean():.4f}")
    print(f"Médiane : {np.median(weights):.4f}")
    print(f"Écart-type : {weights.std():.4f}")
    
    # Percentiles
    print("\n📈 PERCENTILES :")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        val = np.percentile(weights, p)
        print(f"  P{p:2d} : {val:.4f}")
    
    # Distribution
    print("\n📋 DISTRIBUTION PAR PLAGE :")
    bins = [0.0, 0.6, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0]
    for i in range(len(bins) - 1):
        count = np.sum((weights >= bins[i]) & (weights < bins[i+1]))
        pct = (count / len(weights)) * 100
        print(f"  [{bins[i]:.2f} - {bins[i+1]:.2f}[ : {count:5d} ({pct:5.1f}%)")
    
    # Recommandation
    print("\n💡 RECOMMANDATION :")
    if weights.mean() < 0.72:
        print(f"  ⚠️  Moyenne basse ({weights.mean():.4f})")
        print(f"  → Utiliser SIMILARITY_THRESHOLD = 0.70 (permissif)")
    elif weights.mean() < 0.78:
        print(f"  ✅ Moyenne normale ({weights.mean():.4f})")
        print(f"  → Utiliser SIMILARITY_THRESHOLD = 0.72-0.75")
    else:
        print(f"  🎯 Moyenne haute ({weights.mean():.4f})")
        print(f"  → Utiliser SIMILARITY_THRESHOLD = 0.75-0.80")
    
    conn.close()

if __name__ == "__main__":
    diagnose()
