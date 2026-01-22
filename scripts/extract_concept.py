import requests
import json
import re
from pathlib import Path
from tqdm import tqdm

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gpt-oss:20b"
OUTPUT_FILE = Path("data/topics.txt")

# La Carte des Territoires à explorer (180+ Domaines)
DOMAINS = [
    # --- PHILOSOPHIE & ESPRIT (Élargi) ---
    "Métaphysique classique (Spinoza, Leibniz)", "Idéalisme Allemand (Hegel, Kant, Schelling)",
    "Phénoménologie (Husserl, Heidegger)", "Existentialisme (Sartre, Camus)",
    "Philosophie de l'Esprit (Cognition, Conscience)", "Psychologie Analytique (Jung, Archétypes)",
    "Logique Formelle & Paradoxes", "Éthique & Morale", "Esthétique & Théorie de l'Art",
    "Philosophie analytique (Wittgenstein, Russell)", "Philosophie politique (Rawls, Nozick)",
    "Philosophie du langage", "Structuralisme (Lévi-Strauss, Foucault)",
    "Post-structuralisme (Derrida, Deleuze)", "Philosophie des sciences (Kuhn, Popper)",
    "Stoïcisme et philosophie hellénistique", "Philosophie orientale (Confucius, Bouddhisme Zen)",
    
    # --- PHYSIQUE & MATIÈRE (Élargi) ---
    "Thermodynamique & Entropie", "Mécanique Quantique (Concepts clés)",
    "Relativité (Restreinte & Générale)", "Astrophysique & Cosmologie",
    "Théorie du Chaos & Systèmes Dynamiques", "Physique des Particules",
    "Chimie Organique & Moléculaire", "Science des Matériaux",
    "Physique du Solide et États de la matière", "Optique Quantique",
    "Physique Nucléaire", "Supraconductivité", "Mécanique Statistique",
    "Physique des Plasmas", "Cosmologie Quantique", "Théorie des Cordes",
    "Gravité Quantique", "Physique Atomique",
    
    # --- VIVANT & NATURE (Élargi) ---
    "Biologie Évolutive (Darwin, Dawkins)", "Neurosciences & Cerveau",
    "Génétique & ADN", "Écologie & Écosystèmes", "Botanique & Mycologie",
    "Zoologie & Éthologie", "Biologie Cellulaire", "Biologie Moléculaire",
    "Évolution Humaine et Paléoanthropologie", "Virologie et Immunologie",
    "Biologie du Développement", "Biologie Marine", "Éthologie Cognitive",
    "Épigénétique", "Bioinformatique", "Biotechnologies",
    "Anatomie Comparée", "Physiologie Animale",
    
    # --- SYSTÈMES & TECH (Élargi) ---
    "Cybernétique (Wiener, Ashby)", "Théorie de l'Information (Shannon)",
    "Intelligence Artificielle & Réseaux de Neurones", "Cryptographie & Blockchain",
    "Programmation & Algorithmique", "Réseaux & Internet",
    "Mathématiques (Topologie & Géométrie)", "Théorie des Graphes",
    "Informatique Quantique", "Robotique et Automatisation",
    "Vision par Ordinateur", "Traitement du Langage Naturel",
    "Architecture des Ordinateurs", "Sécurité Informatique",
    "Base de Données et Big Data", "Internet des Objets",
    "Réalité Virtuelle et Augmentée", "Bio-inspiration et Biomimétisme",
    
    # --- MATHÉMATIQUES PURES (Nouveau) ---
    "Algèbre Abstraite", "Analyse Complexe", "Théorie des Nombres",
    "Géométrie Différentielle", "Topologie Algébrique", "Logique Mathématique",
    "Théorie des Catégories", "Analyse Fonctionnelle", "Probabilités Avancées",
    "Équations Différentielles", "Mathématiques Discrètes",
    
    # --- HISTOIRE & SOCIÉTÉ (Élargi) ---
    "Histoire Antique (Grèce, Rome, Égypte)", "Moyen-Âge & Alchimie",
    "Renaissance & Humanisme", "Révolution Industrielle",
    "Géopolitique Moderne", "Sociologie (Bourdieu, Durkheim)",
    "Économie & Finance de Marché", "Anthropologie & Mythes",
    "Histoire des Révolutions", "Colonialisme et Post-colonialisme",
    "Histoire des Sciences et Techniques", "Archéologie Préhistorique",
    "Histoire du Droit et des Institutions", "Migrations Humaines",
    "Histoire des Religions", "Économie Comportementale",
    "Théories du Complot", "Mouvements Sociaux Contemporains",
    
    # --- ARTS & CULTURE (Élargi) ---
    "Théorie Musicale & Harmonie", "Histoire de la Peinture",
    "Architecture (Styles & Structures)", "Cinéma & Narration",
    "Littérature Classique", "Poésie & Rhétorique",
    "Science-Fiction & Cyberpunk", "Musique Électronique & Synthèse Sonore",
    "Histoire du Théâtre", "Danse et Chorégraphie",
    "Photographie et Art Numérique", "Bande Dessinée et Manga",
    "Jeux Vidéo et Ludologie", "Design et Arts Appliqués",
    "Littérature Post-moderne", "Art Contemporain et Installations",
    "Culture Pop et Sociétés", "Presse et Médias",
    
    # --- ÉSOTÉRISME & MYSTÈRE (Élargi) ---
    "Hermétisme & Occultisme", "Symbolisme Sacré",
    "Mythologie Comparée", "Spiritualité Orientale (Zen, Tao, Bouddhisme)",
    "Kabbale et Mystique Juive", "Alchimie Occidentale",
    "Franc-Maçonnerie et Sociétés Secrètes", "Chamanisme Traditionnel",
    "Divination et Arts Oraculaires", "Mystères Antiques (Eleusis, Mithra)",
    "Spiritualités Alternatives", "Parapsychologie",
    
    # --- SCIENCES COGNITIVES & LINGUISTIQUE (Nouveau) ---
    "Psychologie Cognitive", "Neurosciences Cognitives",
    "Intelligence Artificielle Symbolique", "Linguistique Générative (Chomsky)",
    "Sémantique et Pragmatique", "Psycholinguistique",
    "Philosophie de l'Esprit", "Cognitive Science des Religions",
    "Neuropsychologie", "Sciences de l'Apprentissage",
    
    # --- INGÉNIERIE & APPLICATIONS (Nouveau) ---
    "Génie Civil et Architecture", "Aérospatial et Aéronautique",
    "Génie Biomédical", "Nanotechnologies",
    "Génie Énergétique", "Robotique Industrielle",
    "Ingénierie des Transports", "Génie de l'Environnement",
    "Technologies Médicales", "Ingénierie des Matériaux",
    
    # --- SCIENCES HUMAINES APPROFONDIES (Nouveau) ---
    "Archéologie Classique", "Paléographie et Manuscrits",
    "Épistémologie et Histoire des Idées", "Démographie Historique",
    "Musicologie Systématique", "Esthétique Philosophique",
    "Théorie Critique (École de Francfort)", "Féminisme et Gender Studies",
    "Cultural Studies", "Post-colonial Studies",
    
    # --- SCIENCES DE LA TERRE & ESPACE (Nouveau) ---
    "Géologie Structurale", "Climatologie et Météorologie",
    "Océanographie Physique", "Planétologie Comparée",
    "Volcanologie", "Sismologie", "Astrobiologie",
    "Géophysique", "Paléoclimatologie",
    
    # --- NOUVELLES FRONTIÈRES (Nouveau) ---
    "Transhumanisme et Post-humanisme", "Bioéthique et Éthique Médicale",
    "Écologie Profonde", "Théorie des Systèmes Complexes",
    "Science des Réseaux Sociaux", "Économie de l'Attention",
    "Cryobiologie", "Exoplanétologie",
    "Intelligence Artificielle Générale", "Conscience Artificielle"
]

def mine_concepts():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    all_concepts = set()
    print(f"⛏️  Début de l'extraction minière sur {len(DOMAINS)} domaines...")
    print(f"🤖 Modèle: {MODEL_NAME}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        
        pbar = tqdm(DOMAINS)
        for domain in pbar:
            pbar.set_description(f"Mining: {domain[:25]}...")
            
            prompt = (
                f"Liste uniquement les 80 à 100 concepts techniques, théoriques ou clés "
                f"appartenant au domaine : '{domain}'. "
                f"Format de sortie : une simple liste de mots ou expressions séparés par des virgules. "
                f"Pas de numérotation, pas de description, pas de phrase d'intro. "
                f"Exemple: Concept A, Concept B, Concept C"
            )

            try:
                response = requests.post(OLLAMA_URL, json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024
                    }
                })
                
                if response.status_code == 200:
                    content = response.json()['response']
                    
                    # Nettoyage amélioré
                    content = content.replace('\n', ',')
                    raw_list = content.split(',')
                    
                    domain_count = 0
                    for item in raw_list:
                        clean_item = item.strip()
                        # Filtres de qualité améliorés
                        if (len(clean_item) > 2 and
                            len(clean_item) < 50 and
                            not clean_item.isdigit() and
                            clean_item[0].isupper() and
                            not any(word in clean_item.lower() for word in ['exemple', 'example', 'liste', 'concept']) and
                            not clean_item.endswith(':')):
                            
                            if clean_item not in all_concepts:
                                all_concepts.add(clean_item)
                                f.write(clean_item + "\n")
                                domain_count += 1
                    
                    f.flush()
                    
                else:
                    print(f"❌ Erreur API sur {domain}")

            except Exception as e:
                print(f"❌ Exception sur {domain}: {e}")
                continue

    print(f"\n✅ Terminé ! {len(all_concepts)} concepts uniques extraits et sauvegardés dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    mine_concepts()