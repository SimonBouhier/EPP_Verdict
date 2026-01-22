"""
LYRA GENESIS - THE WEAVER (LE TISSERAND) v2.0
==============================================

"Nous ne tissons pas seulement des données, nous révélons la géométrie de la pensée."

AMÉLIORATIONS :
- Gestion robuste des erreurs Ollama avec retry exponentiel
- Calcul matriciel optimisé (mémoire + performance) 
- Métriques détaillées et diagnostics
- Sauvegarde intermédiaire contre la perte de données
- Gestion des embeddings défaillants
- Visualisation en temps réel de la progression
"""

import sqlite3
import requests
import numpy as np
import time
import sys
import json
import logging
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from typing import List, Tuple, Optional
import hashlib

# ============================================================================
# CONFIGURATION SACRÉE
# ============================================================================

# Chemins
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "topics.txt"
DB_PATH = BASE_DIR / "data" / "ispace.db"
EMBEDDINGS_CACHE = BASE_DIR / "data" / "embeddings_cache.json"

# L'Oracle Vectoriel
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mxbai-embed-large"  # Le cartographe

# La Physique du Lien
SIMILARITY_THRESHOLD = 0.70  # Cosinus: seuil final pour accepter un lien
MIN_SIMILARITY = 0.65  # Pré-filtrage grossier
MAX_EDGES_PER_NODE = 50  # Éviter la surcharge cognitive

# Performance
SQL_BATCH_SIZE = 2000
EMBEDDING_BATCH_SIZE = 32  # Lot pour Ollama
MAX_RETRIES = 3
RETRY_DELAY = 2

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / "data" / "weaver.log"),
        logging.StreamHandler()
    ]
)

class TheWeaver:
    def __init__(self):
        self.concepts = []
        self.embeddings = []
        self.embeddings_cache = {}
        self.failed_concepts = []
        self.start_time = time.time()
        self.logger = logging.getLogger('Weaver')

    def log(self, message: str, icon: str = "✨", level: str = "info"):
        """Journalisation avancée avec sauvegarde."""
        elapsed = time.time() - self.start_time
        formatted_message = f"{icon} [{elapsed:.2f}s] {message}"
        
        getattr(self.logger, level)(message)
        print(formatted_message)

    def load_embeddings_cache(self):
        """Charge le cache des embeddings pour éviter de ressaisir les mêmes concepts."""
        if EMBEDDINGS_CACHE.exists():
            with open(EMBEDDINGS_CACHE, 'r', encoding='utf-8') as f:
                self.embeddings_cache = json.load(f)
            self.log(f"Cache chargé : {len(self.embeddings_cache)} embeddings en mémoire", "💾")

    def save_embeddings_cache(self):
        """Sauvegarde le cache des embeddings."""
        with open(EMBEDDINGS_CACHE, 'w', encoding='utf-8') as f:
            json.dump(self.embeddings_cache, f, ensure_ascii=False, indent=2)
        self.log(f"Cache sauvegardé : {len(self.embeddings_cache)} embeddings", "💾")

    def get_concept_hash(self, concept: str) -> str:
        """Génère un hash unique pour le concept."""
        return hashlib.md5(concept.encode('utf-8')).hexdigest()

    def load_concepts(self):
        """Charge et valide les concepts."""
        target_file = INPUT_FILE
        
        if not target_file.exists():
            self.log(f"ERREUR: Impossible de trouver {target_file}", "💀", "error")
            sys.exit(1)

        self.log(f"Lecture des concepts : {target_file}", "📖")
        
        with open(target_file, 'r', encoding='utf-8') as f:
            raw_lines = [line.strip() for line in f if line.strip()]
            self.concepts = sorted(list(set(raw_lines)))
            
        # Filtrage de qualité
        initial_count = len(self.concepts)
        self.concepts = [c for c in self.concepts if len(c) >= 3 and len(c) <= 100]
        
        self.log(f"Concepts chargés : {initial_count} → {len(self.concepts)} après filtrage", "🧠")

    def fetch_single_embedding(self, concept: str, retry_count: int = 0) -> Optional[List[float]]:
        """Récupère un embedding avec gestion robuste des erreurs."""
        concept_hash = self.get_concept_hash(concept)
        
        # Vérification du cache
        if concept_hash in self.embeddings_cache:
            return self.embeddings_cache[concept_hash]

        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": MODEL_NAME,
                "prompt": concept
            }, timeout=60)
            
            if resp.status_code == 200:
                vector = resp.json().get("embedding")
                if vector and len(vector) > 0:
                    # Validation de la dimension
                    if len(vector) == 1024:  # Dimension typique pour mxbai-embed-large
                        self.embeddings_cache[concept_hash] = vector
                        return vector
                    else:
                        self.log(f"Dimension invalide pour '{concept}': {len(vector)}", "⚠️", "warning")
                else:
                    self.log(f"Embedding vide pour '{concept}'", "⚠️", "warning")
            else:
                self.log(f"Erreur HTTP {resp.status_code} pour '{concept}'", "⚠️", "warning")

        except requests.exceptions.Timeout:
            self.log(f"Timeout pour '{concept}'", "⏰", "warning")
        except Exception as e:
            self.log(f"Exception pour '{concept}': {e}", "⚠️", "warning")

        # Retry logic
        if retry_count < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** retry_count)  # Backoff exponentiel
            self.log(f"Retry {retry_count + 1}/{MAX_RETRIES} dans {delay}s pour '{concept}'", "🔄")
            time.sleep(delay)
            return self.fetch_single_embedding(concept, retry_count + 1)
        else:
            self.failed_concepts.append(concept)
            self.log(f"Échec définitif pour '{concept}'", "❌", "error")
            return None

    def fetch_embeddings_batch(self):
        """Récupère les embeddings par lots pour optimisation."""
        self.log(f"Début de la vectorisation avec {MODEL_NAME}...", "📡")
        self.load_embeddings_cache()
        
        concepts_to_process = []
        for concept in self.concepts:
            concept_hash = self.get_concept_hash(concept)
            if concept_hash not in self.embeddings_cache:
                concepts_to_process.append(concept)

        self.log(f"{len(concepts_to_process)} nouveaux concepts à vectoriser", "🔍")

        # Barre de progression pour les nouveaux concepts
        pbar = tqdm(concepts_to_process, desc="Vectorisation", unit="concept")
        
        successful = 0
        for concept in pbar:
            vector = self.fetch_single_embedding(concept)
            if vector is not None:
                successful += 1
                pbar.set_postfix(success=f"{successful}/{len(concepts_to_process)}")

        # Sauvegarde périodique du cache
        self.save_embeddings_cache()

        # Construction du tableau final d'embeddings
        valid_concepts = []
        valid_embeddings = []
        
        for concept in self.concepts:
            concept_hash = self.get_concept_hash(concept)
            if concept_hash in self.embeddings_cache:
                valid_concepts.append(concept)
                valid_embeddings.append(self.embeddings_cache[concept_hash])

        self.concepts = valid_concepts
        self.embeddings = np.array(valid_embeddings)
        
        # Rapport final
        success_rate = (len(self.concepts) / len(self.concepts + self.failed_concepts)) * 100
        self.log(f"Vectorisation terminée: {len(self.embeddings)}/{len(self.concepts) + len(self.failed_concepts)} concepts ({success_rate:.1f}%)", "💎")
        
        if self.failed_concepts:
            self.log(f"Concepts échoués: {len(self.failed_concepts)}", "⚠️")
            with open(BASE_DIR / "data" / "failed_concepts.txt", 'w', encoding='utf-8') as f:
                for concept in self.failed_concepts:
                    f.write(concept + "\n")

    def compute_similarity_matrix_optimized(self) -> np.ndarray:
        """Calcule la matrice de similarité de manière optimisée (cosinus)."""
        self.log("Calcul de la matrice de similarité cosinus...", "📐")
        
        # Normalisation L2 (CRITIQUE pour cosinus)
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # Sécurité: éviter division par zéro
        normalized = self.embeddings / norms
        
        # Vérification: tous les vecteurs doivent avoir norme 1
        check_norms = np.linalg.norm(normalized, axis=1)
        if not np.allclose(check_norms, 1.0, atol=1e-6):
            self.log(f"⚠️ Avertissement: normalisation incomplète (min={check_norms.min():.4f}, max={check_norms.max():.4f})", "⚠️", "warning")
        
        # Calcul par blocs pour économiser la mémoire
        n = len(self.concepts)
        block_size = 1000  # Ajuster selon la RAM disponible
        similarity_matrix = np.zeros((n, n), dtype=np.float32)
        
        for i in tqdm(range(0, n, block_size), desc="Calcul par blocs"):
            i_end = min(i + block_size, n)
            for j in range(0, n, block_size):
                j_end = min(j + block_size, n)
                block = np.dot(normalized[i:i_end], normalized[j:j_end].T)
                similarity_matrix[i:i_end, j:j_end] = block
        
        # Vérification: les valeurs de similarité doivent être entre -1 et 1
        self.log(f"Similarité: min={similarity_matrix.min():.4f}, max={similarity_matrix.max():.4f}", "ℹ️")
        if similarity_matrix.max() > 1.01 or similarity_matrix.min() < -1.01:
            self.log(f"🚨 ERREUR: Similarité hors limites [-1, 1]!", "🚨", "error")
        
        return similarity_matrix

    def create_database_schema(self, conn: sqlite3.Connection):
        """Crée le schéma de base de données optimisé (compatible avec ISpaceDB)."""
        c = conn.cursor()
        
        # Nettoyage
        c.execute("DROP TABLE IF EXISTS concepts")
        c.execute("DROP TABLE IF EXISTS relations")
        c.execute("DROP TABLE IF EXISTS metadata")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-64000")  # 64MB cache

        # Schéma principal (compatible avec database/engine.py)
        c.execute("""
            CREATE TABLE concepts (
                id TEXT PRIMARY KEY,
                rho_static REAL DEFAULT 0.5,
                degree INTEGER DEFAULT 0,
                embedding BLOB,
                embedding_model TEXT,
                created_at REAL NOT NULL,
                last_accessed REAL,
                access_count INTEGER DEFAULT 0
            )
        """)
        
        c.execute("""
            CREATE TABLE relations (
                source TEXT,
                target TEXT,
                weight REAL NOT NULL,
                kappa REAL DEFAULT 0.5,
                created_at REAL NOT NULL,
                PRIMARY KEY (source, target),
                FOREIGN KEY (source) REFERENCES concepts(id),
                FOREIGN KEY (target) REFERENCES concepts(id)
            )
        """)
        
        c.execute("""
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Index optimisés
        c.execute("CREATE INDEX idx_concepts_id ON concepts(id)")
        c.execute("CREATE INDEX idx_concepts_rho ON concepts(rho_static DESC)")
        c.execute("CREATE INDEX idx_concepts_degree ON concepts(degree DESC)")
        c.execute("CREATE INDEX idx_relations_source ON relations(source, weight DESC)")
        c.execute("CREATE INDEX idx_relations_target ON relations(target, weight DESC)")
        c.execute("CREATE INDEX idx_relations_weight ON relations(weight DESC)")

        # Métadonnées système
        import time
        metadata = {
            "version": "2.0",
            "created_at": str(time.time()),
            "model_used": MODEL_NAME,
            "similarity_threshold": str(SIMILARITY_THRESHOLD),
            "total_concepts": str(len(self.concepts))
        }
        
        for key, value in metadata.items():
            c.execute("INSERT INTO metadata VALUES (?, ?)", (key, value))

        conn.commit()

    def weave_and_store(self):
        """Tissage optimisé avec métriques détaillées."""
        self.log("Début du tissage de l'hyper-espace...", "🌌")
        
        # Préparation de la base
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        self.create_database_schema(conn)
        c = conn.cursor()

        # 1. Ancrage des nœuds
        self.log("Ancrage des concepts...", "📍")
        import time
        now = time.time()
        node_data = [(concept, 0.5, 0, None, None, now, None, 0) 
                    for concept in self.concepts]
        c.executemany("INSERT INTO concepts VALUES (?, ?, ?, ?, ?, ?, ?, ?)", node_data)
        conn.commit()

        # 2. Calcul de similarité
        similarity_matrix = self.compute_similarity_matrix_optimized()

        # 3. Tissage des liens avec filtrage intelligent
        self.log("Création des synapses...", "⚡")
        
        edges_buffer = []
        node_degrees = {concept: 0 for concept in self.concepts}
        
        # Pré-calcul des meilleures connexions par nœud
        for i, source in enumerate(tqdm(self.concepts, desc="Tri des liens")):
            similarities = [(j, similarity_matrix[i, j]) 
                          for j in range(len(self.concepts)) 
                          if i != j and similarity_matrix[i, j] >= MIN_SIMILARITY]
            
            # Trier et garder les meilleures
            similarities.sort(key=lambda x: x[1], reverse=True)
            top_similarities = similarities[:MAX_EDGES_PER_NODE]
            
            for j, weight in top_similarities:
                if weight < SIMILARITY_THRESHOLD:
                    continue
                    
                target = self.concepts[j]
                # Vérification: weight DOIT être entre 0 et 1
                if weight < 0 or weight > 1.0:
                    self.log(f"🚨 Poids invalide pour {source} -> {target}: {weight}", "🚨", "error")
                    continue
                    
                kappa_req = round(1.0 - weight + 0.2, 3)
                
                # Convertir en float Python standard (pas numpy.float32)
                weight_float = float(weight)
                kappa_req_float = float(kappa_req)
                
                import time
                edges_buffer.append((source, target, weight_float, kappa_req_float, time.time()))
                node_degrees[source] += 1
                node_degrees[target] += 1
                
                if len(edges_buffer) >= SQL_BATCH_SIZE:
                    c.executemany("INSERT OR IGNORE INTO relations VALUES (?, ?, ?, ?, ?)", edges_buffer)
                    edges_buffer = []
                    conn.commit()

        # Insertion finale
        if edges_buffer:
            c.executemany("INSERT OR IGNORE INTO relations VALUES (?, ?, ?, ?, ?)", edges_buffer)
            conn.commit()

        # Mise à jour des degrés
        self.log("Mise à jour des métriques des nœuds...", "📊")
        # Calculer le rho_static (normalized degree)
        max_degree = max(node_degrees.values()) if node_degrees else 1
        degree_data = [
            (degree / max_degree if max_degree > 0 else 0, degree, concept)
            for concept, degree in node_degrees.items()
        ]
        c.executemany("UPDATE concepts SET rho_static = ?, degree = ? WHERE id = ?", degree_data)
        conn.commit()

        # 5. Statistiques détaillées
        self.generate_detailed_stats(conn, len(self.concepts))

        conn.close()

    def generate_detailed_stats(self, conn: sqlite3.Connection, total_concepts: int):
        """Génère des statistiques détaillées sur le réseau."""
        c = conn.cursor()
        
        # Statistiques de base
        c.execute("SELECT COUNT(*) FROM relations")
        total_edges = c.fetchone()[0]
        
        c.execute("SELECT AVG(weight) FROM relations")
        avg_weight = c.fetchone()[0] or 0
        
        c.execute("SELECT MAX(degree) FROM concepts")
        max_degree = c.fetchone()[0] or 0
        
        c.execute("SELECT AVG(degree) FROM concepts")
        avg_degree = c.fetchone()[0] or 0
        
        # Distribution des poids
        c.execute("""
            SELECT 
                COUNT(*) as count,
                CASE 
                    WHEN weight >= 0.9 THEN 'Très fort (0.9+)'
                    WHEN weight >= 0.8 THEN 'Fort (0.8-0.9)'
                    WHEN weight >= 0.7 THEN 'Moyen (0.7-0.8)'
                    ELSE 'Faible (<0.7)'
                END as strength
            FROM relations 
            GROUP BY strength
            ORDER BY weight DESC
        """)
        weight_distribution = c.fetchall()

        # Affichage du rapport
        print("\n" + "="*70)
        print("🌍  RAPPORT DÉTAILLÉ DU TISSAGE  🌍")
        print("="*70)
        print(f"📊 Concepts intégrés    : {total_concepts}")
        print(f"🔗 Synapses créées      : {total_edges}")
        print(f"📈 Densité du réseau    : {total_edges/total_concepts:.2f} liens/concept")
        print(f"🎯 Poids moyen          : {avg_weight:.3f}")
        print(f"📋 Degré maximal        : {max_degree}")
        print(f"📋 Degré moyen          : {avg_degree:.1f}")
        print(f"💾 Fichier de base      : {DB_PATH}")
        
        print("\n📋 DISTRIBUTION DES LIENS PAR FORCE :")
        for count, strength in weight_distribution:
            percentage = (count / total_edges) * 100
            print(f"   {strength:<20} : {count:>4} liens ({percentage:>5.1f}%)")

        print("="*70)

        # Sauvegarde des métriques avancées
        c.execute("INSERT INTO metadata VALUES ('total_edges', ?)", (str(total_edges),))
        c.execute("INSERT INTO metadata VALUES ('average_weight', ?)", (str(avg_weight),))
        c.execute("INSERT INTO metadata VALUES ('max_degree', ?)", (str(max_degree),))
        c.execute("INSERT INTO metadata VALUES ('average_degree', ?)", (str(avg_degree),))
        conn.commit()

def main():
    """Point d'entrée principal avec gestion d'erreur globale."""
    print("\n🔮 LYRA GENESIS v2.0: LE TISSERAND INTELLIGENT\n")
    
    try:
        weaver = TheWeaver()
        weaver.load_concepts()
        weaver.fetch_embeddings_batch()
        
        if len(weaver.concepts) == 0:
            weaver.log("Aucun concept valide à traiter. Arrêt.", "💀", "error")
            return
            
        weaver.weave_and_store()
        weaver.log("Tissage terminé avec succès!", "🎉")
        
    except KeyboardInterrupt:
        weaver.log("Interruption utilisateur. Sauvegarde du cache...", "⏹️", "warning")
        weaver.save_embeddings_cache()
    except Exception as e:
        weaver.log(f"ERREUR CRITIQUE: {e}", "💀", "error")
        sys.exit(1)

if __name__ == "__main__":
    main()