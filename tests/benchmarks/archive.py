"""
Benchmark Data Archive System
==============================

Système d'archivage complet pour les données de benchmark.
Stocke tout pour analyse ultérieure :
- Réponses brutes du modèle
- Embeddings (query + response)
- Métriques calculées
- Metadata temporelle
- Contexte d'exécution
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib


class BenchmarkArchive:
    """Archive persistante pour données de benchmark"""
    
    def __init__(self, archive_dir: str = "benchmark_results"):
        """
        Initialise le système d'archivage.
        
        Args:
            archive_dir: Répertoire d'archivage
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(exist_ok=True)
        
        # Base de données SQLite pour indexation
        self.db_path = self.archive_dir / "benchmark_archive.db"
        self._init_database()
    
    def _init_database(self):
        """Crée les tables d'archivage si absentes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table maîtresse des runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                benchmark_type TEXT NOT NULL,
                config TEXT NOT NULL,
                status TEXT DEFAULT 'in_progress',
                completed_at REAL
            )
        """)
        
        # Table des messages/requêtes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                level INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                query_embeddings BLOB,
                
                response_text TEXT,
                response_hash TEXT,
                response_embeddings BLOB,
                
                latency_ms REAL,
                tokens_prompt INTEGER,
                tokens_response INTEGER,
                
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)
        
        # Table des métriques calculées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                msg_id TEXT NOT NULL,
                coherence REAL,
                tension REAL,
                fit REAL,
                pressure REAL,
                stability REAL,
                adjustments_triggered BOOLEAN,
                memory_echo TEXT,
                
                FOREIGN KEY (msg_id) REFERENCES messages(msg_id)
            )
        """)
        
        # Table des métadonnées contextuelles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS context_metadata (
                metadata_id TEXT PRIMARY KEY,
                msg_id TEXT NOT NULL,
                concepts_injected TEXT,
                graph_weight REAL,
                session_length INTEGER,
                profile_used TEXT,
                llm_model TEXT,
                ollama_version TEXT,
                
                FOREIGN KEY (msg_id) REFERENCES messages(msg_id)
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_run ON messages(run_id, turn_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_level ON messages(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_msg ON metrics(msg_id)")
        
        conn.commit()
        conn.close()
    
    def create_run(
        self,
        run_id: str,
        benchmark_type: str,
        config: Dict[str, Any]
    ) -> str:
        """
        Crée une nouvelle session de benchmark.
        
        Args:
            run_id: Identifiant unique du run
            benchmark_type: Type (e.g., 'phase_2', 'phase_3', 'e2e')
            config: Configuration du benchmark
            
        Returns:
            run_id pour référence ultérieure
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO runs (run_id, timestamp, benchmark_type, config, status)
            VALUES (?, ?, ?, ?, 'in_progress')
        """, (
            run_id,
            datetime.now().timestamp(),
            benchmark_type,
            json.dumps(config)
        ))
        
        conn.commit()
        conn.close()
        
        return run_id
    
    def archive_message(
        self,
        run_id: str,
        turn_number: int,
        level: int,
        query_text: str,
        query_embeddings: Optional[List[float]] = None,
        response_text: Optional[str] = None,
        response_embeddings: Optional[List[float]] = None,
        latency_ms: Optional[float] = None,
        tokens: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Archive une paire query/response avec tous les détails.
        
        Args:
            run_id: ID du run
            turn_number: Numéro du tour
            level: Niveau de conscience
            query_text: Texte de la requête
            query_embeddings: Embeddings de la requête (1024D pour Phase 3)
            response_text: Réponse du modèle
            response_embeddings: Embeddings de la réponse
            latency_ms: Latence totale
            tokens: Dict avec 'prompt', 'response', 'total'
            
        Returns:
            msg_id pour référence
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Générer identifiants
        msg_id = self._generate_id(f"{run_id}_{turn_number}_{level}")
        query_hash = self._hash_text(query_text)
        response_hash = self._hash_text(response_text) if response_text else None
        
        # Sérialiser embeddings
        query_emb_blob = self._serialize_embeddings(query_embeddings)
        response_emb_blob = self._serialize_embeddings(response_embeddings)
        
        # Tokens par défaut
        if tokens is None:
            tokens = {'prompt': 0, 'response': 0, 'total': 0}
        
        # Insérer message
        cursor.execute("""
            INSERT INTO messages (
                msg_id, run_id, turn_number, level,
                query_text, query_hash, query_embeddings,
                response_text, response_hash, response_embeddings,
                latency_ms, tokens_prompt, tokens_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            msg_id, run_id, turn_number, level,
            query_text, query_hash, query_emb_blob,
            response_text, response_hash, response_emb_blob,
            latency_ms, tokens.get('prompt', 0), tokens.get('response', 0)
        ))
        
        conn.commit()
        conn.close()
        
        # Créer fichier JSON brut pour inspection rapide
        self._save_message_json(msg_id, {
            'run_id': run_id,
            'turn': turn_number,
            'level': level,
            'query': query_text,
            'response': response_text,
            'latency_ms': latency_ms,
            'tokens': tokens,
            'timestamp': datetime.now().isoformat()
        })
        
        return msg_id
    
    def archive_metrics(
        self,
        msg_id: str,
        coherence: float,
        tension: float,
        fit: float,
        pressure: float,
        stability: float,
        adjustments_triggered: bool = False,
        memory_echo: Optional[str] = None
    ) -> str:
        """Archive les métriques calculées pour ce message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metric_id = self._generate_id(f"{msg_id}_metrics")
        
        cursor.execute("""
            INSERT INTO metrics (
                metric_id, msg_id,
                coherence, tension, fit, pressure, stability,
                adjustments_triggered, memory_echo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metric_id, msg_id,
            coherence, tension, fit, pressure, stability,
            adjustments_triggered, memory_echo
        ))
        
        conn.commit()
        conn.close()
        
        return metric_id
    
    def archive_context(
        self,
        msg_id: str,
        concepts_injected: Optional[List[str]] = None,
        graph_weight: float = 0.0,
        session_length: int = 0,
        profile_used: str = "balanced",
        llm_model: str = "gpt-oss:20b",
        ollama_version: str = ""
    ) -> str:
        """Archive le contexte d'exécution du message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metadata_id = self._generate_id(f"{msg_id}_context")
        
        cursor.execute("""
            INSERT INTO context_metadata (
                metadata_id, msg_id,
                concepts_injected, graph_weight, session_length,
                profile_used, llm_model, ollama_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata_id, msg_id,
            json.dumps(concepts_injected or []),
            graph_weight,
            session_length,
            profile_used,
            llm_model,
            ollama_version
        ))
        
        conn.commit()
        conn.close()
        
        return metadata_id
    
    def finalize_run(self, run_id: str, status: str = "completed"):
        """Marque un run comme complété"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE runs
            SET status = ?, completed_at = ?
            WHERE run_id = ?
        """, (status, datetime.now().timestamp(), run_id))
        
        conn.commit()
        conn.close()
    
    def export_run(self, run_id: str, output_path: Optional[Path] = None) -> Path:
        """
        Exporte une session complète en JSONL.
        
        Args:
            run_id: ID du run à exporter
            output_path: Chemin de destination (défaut: archive_dir/run_id.jsonl)
            
        Returns:
            Chemin du fichier exporté
        """
        if output_path is None:
            output_path = self.archive_dir / f"{run_id}_export.jsonl"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Récupérer tous les messages avec leurs métriques
        cursor.execute("""
            SELECT m.*, me.coherence, me.tension, me.fit, me.pressure, me.stability,
                   me.adjustments_triggered, me.memory_echo,
                   cm.concepts_injected, cm.graph_weight, cm.session_length,
                   cm.profile_used, cm.llm_model
            FROM messages m
            LEFT JOIN metrics me ON m.msg_id = me.msg_id
            LEFT JOIN context_metadata cm ON m.msg_id = cm.msg_id
            WHERE m.run_id = ?
            ORDER BY m.turn_number
        """, (run_id,))
        
        with open(output_path, 'w') as f:
            for row in cursor.fetchall():
                record = self._row_to_dict(row, cursor.description)
                f.write(json.dumps(record) + '\n')
        
        conn.close()
        
        return output_path
    
    def query_run_summary(self, run_id: str) -> Dict[str, Any]:
        """Récupère un résumé du run"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Récupérer info du run
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        run_row = cursor.fetchone()
        
        if not run_row:
            return {}
        
        run_data = self._row_to_dict(run_row, cursor.description)
        
        # Statistiques des messages
        cursor.execute("""
            SELECT COUNT(*) as count, level,
                   AVG(latency_ms) as avg_latency,
                   MAX(latency_ms) as max_latency,
                   MIN(latency_ms) as min_latency
            FROM messages
            WHERE run_id = ?
            GROUP BY level
        """, (run_id,))
        
        messages_stats = []
        for row in cursor.fetchall():
            messages_stats.append(self._row_to_dict(row, cursor.description))
        
        # Statistiques des métriques
        cursor.execute("""
            SELECT AVG(coherence) as avg_coherence,
                   AVG(tension) as avg_tension,
                   AVG(fit) as avg_fit,
                   AVG(pressure) as avg_pressure,
                   AVG(stability) as avg_stability,
                   COUNT(*) as samples
            FROM metrics
            WHERE msg_id IN (SELECT msg_id FROM messages WHERE run_id = ?)
        """, (run_id,))
        
        metrics_row = cursor.fetchone()
        metrics_stats = self._row_to_dict(metrics_row, cursor.description)
        
        conn.close()
        
        return {
            'run': run_data,
            'messages_stats': messages_stats,
            'metrics_stats': metrics_stats
        }
    
    def retrieve_message_data(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Récupère toutes les données d'un message spécifique"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.*, me.*, cm.*
            FROM messages m
            LEFT JOIN metrics me ON m.msg_id = me.msg_id
            LEFT JOIN context_metadata cm ON m.msg_id = cm.msg_id
            WHERE m.msg_id = ?
        """, (msg_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_dict(row, cursor.description)
    
    # ========== HELPERS ==========
    
    def _generate_id(self, seed: str) -> str:
        """Génère un ID unique"""
        return hashlib.md5(seed.encode()).hexdigest()[:16]
    
    def _hash_text(self, text: Optional[str]) -> Optional[str]:
        """Hash du texte pour deduplication"""
        if not text:
            return None
        return hashlib.sha256(text.encode()).hexdigest()
    
    def _serialize_embeddings(self, embeddings: Optional[List[float]]) -> Optional[bytes]:
        """Sérialise les embeddings en bytes"""
        if not embeddings:
            return None
        import struct
        return struct.pack(f'{len(embeddings)}f', *embeddings)
    
    def _deserialize_embeddings(self, blob: Optional[bytes]) -> Optional[List[float]]:
        """Désérialise les embeddings"""
        if not blob:
            return None
        import struct
        dim = len(blob) // 4
        return list(struct.unpack(f'{dim}f', blob))
    
    def _save_message_json(self, msg_id: str, data: Dict):
        """Sauvegarde le message en JSON pour inspection"""
        msg_file = self.archive_dir / f"{msg_id}.json"
        with open(msg_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def _row_to_dict(self, row: tuple, description) -> Dict:
        """Convertit une ligne SQLite en dict"""
        if row is None:
            return {}
        
        result = {}
        for i, desc in enumerate(description):
            val = row[i]
            # Convertir bytes en base64 pour JSON
            if isinstance(val, bytes):
                import base64
                val = base64.b64encode(val).decode('ascii')
            result[desc[0]] = val
        
        return result
