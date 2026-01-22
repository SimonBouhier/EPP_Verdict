"""
LYRA CLEAN - BRAIN PROBE
========================
Test unitaire du moteur de récupération (Retrieval Engine).
Vérifie que la base de données répond correctement aux stimuli.
"""
import asyncio
import sys
from pathlib import Path

# Ajout du dossier parent au path pour importer 'database' et 'core'
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.engine import get_db

async def probe_concept(concept: str, db):
    print(f"\n🧠 STIMULUS : '{concept}'")
    
    # 1. Vérifier si le concept existe
    node = await db.get_concept(concept)
    if not node:
        print(f"   ❌ Concept inconnu dans le I-Space.")
        return

    print(f"   ✅ Concept identifié (Rho: {node.get('rho', 0):.2f}, Degree: {node.get('degree', 0)})")

    # 2. Récupérer les voisins (Synapses)
    neighbors = await db.get_neighbors(concept, limit=10)
    
    print(f"   ⚡ Activation de {len(neighbors)} synapses :")
    for neighbor in neighbors:
        weight = neighbor.get('weight', 0)
        target = neighbor.get('target', '?')
        kappa = neighbor.get('kappa_req', 0)
        bar_len = int(weight * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"      -> {target:<30} {bar} ({weight:.3f}) [κ req: {kappa:.2f}]")

async def main():
    print("🔮 INITIALISATION DU SYSTÈME NEURAL...")
    
    # Test sur 3 concepts clés de ta liste pour voir la variété
    # Tu peux changer ces mots selon tes envies
    test_concepts = [
        "Hegel",             # Philosophie (Noyau dur)
        "Entropie",          # Physique (Systémique)
        "Conscience artificielle" # Meta (Le futur)
    ]
    
    try:
        db = await get_db()
        for c in test_concepts:
            await probe_concept(c, db)
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🏁 Test terminé.")

if __name__ == "__main__":
    # Windows loop policy fix (si nécessaire)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())