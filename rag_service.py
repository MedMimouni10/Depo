# services/rag_service.py
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack.utils import Secret

# NOUVEAUX IMPORTS : Les composants OpenAI natifs de Haystack
from haystack.components.generators import OpenAIGenerator
from haystack.components.embedders import OpenAITextEmbedder, OpenAIDocumentEmbedder

# Imports pour l'indexation
from haystack.components.converters import PyPDFToDocument
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy


import json
import re

from services.learning_service import get_llm



# On utilise une variable globale pour ne charger le pipeline qu'une seule fois au démarrage
_rag_pipeline = None

def get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        # Connexion à ta base de données Docker (Port 5434)
        document_store = PgvectorDocumentStore(
            connection_string=Secret.from_token("postgresql://admin:adminpassword@localhost:5434/alten_knowledge_base"),
            table_name="haystack_docs",
            embedding_dimension=768  # ⚠️ MODIFIÉ POUR NOMIC (768 au lieu de 384)
        )
        
        template = """
        Tu es un assistant expert pour la société ALTEN.
        Réponds à la question en te basant UNIQUEMENT sur les documents fournis ci-dessous.
        Si la réponse ne s'y trouve pas, dis "Je n'ai pas l'information dans votre périmètre autorisé".

        Documents:
        {% for doc in documents %}
            Fichier : {{ doc.meta.get('file_name', 'Inconnu') }}
            Extrait : {{ doc.content }}
        {% endfor %}

        Question: {{ question }}
        Réponse (en français) :
        """
        
        _rag_pipeline = Pipeline()
        
        # NOUVEAU : Embedder de texte connecté au serveur 800 (Nomic)
        _rag_pipeline.add_component("text_embedder", OpenAITextEmbedder(
            api_key=Secret.from_token("EMPTY"),
            api_base_url="http://itgfrapapp800.prod.altengroup.dir:4200/v1",
            model="nomic-embed-text:latest"
        ))
        
        _rag_pipeline.add_component("retriever", PgvectorEmbeddingRetriever(document_store=document_store, top_k=3))
        _rag_pipeline.add_component("prompt_builder", PromptBuilder(template=template))
        
        # NOUVEAU : Générateur LLM connecté au serveur 801 (Gemma-3)
        _rag_pipeline.add_component("llm", OpenAIGenerator(
            api_key=Secret.from_token("EMPTY"),
            api_base_url="http://itgfrapapp801.prod.altengroup.dir:9000/v1",
            model="ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g",
            generation_kwargs={"max_tokens": 500, "temperature": 0.1}
        ))

        # Connexions du pipeline
        _rag_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        _rag_pipeline.connect("retriever", "prompt_builder.documents")
        _rag_pipeline.connect("prompt_builder", "llm")

    return _rag_pipeline

def generer_reponse_rag(question, liste_fichiers_autorises):
    """
    Interroge le LLM en limitant strictement la recherche à une liste de fichiers.
    """
    if not liste_fichiers_autorises:
        return "Vous n'avez accès à aucun document pour répondre à cette question.", []

    pipeline = get_rag_pipeline()
    
    # LE PONT MAGIQUE : Haystack va filtrer dynamiquement selon ce que le SQL a autorisé !
    dynamic_filter = {
        "field": "meta.file_name", 
        "operator": "in", 
        "value": liste_fichiers_autorises
    }

    try:
        result = pipeline.run({
            "text_embedder": {"text": question},
            "retriever": {"filters": dynamic_filter},
            "prompt_builder": {"question": question}
        }, include_outputs_from={"retriever"})
        
        reponse = result.get("llm", {}).get("replies", ["Erreur lors de la génération."])[0]
        sources = result.get("retriever", {}).get("documents", [])
        
        return reponse, sources
    except Exception as e:
        return f"Erreur technique : {str(e)}", []
    
# =========================================================================
# PIPELINE D'INDEXATION (Pour l'interface Admin)
# =========================================================================

def indexer_document_dans_haystack(file_path, file_name, cellule_nom):

    """
    Prend un fichier local, le découpe, génère les embeddings via le modèle Alten 
    et le stocke dans la table vectorielle principale.
    """
    document_store = PgvectorDocumentStore(
        connection_string=Secret.from_token("postgresql://admin:adminpassword@localhost:5434/alten_knowledge_base"),
        table_name="haystack_docs",
        embedding_dimension=768 # ⚠️ MODIFIÉ POUR NOMIC
    )
    
    converter = PyPDFToDocument()
    splitter = DocumentSplitter(split_by="word", split_length=300, split_overlap=30)
    
    # 1. Extraction du texte du PDF
    docs = converter.run(sources=[file_path])["documents"]
    
    # 2. Injection des métadonnées cruciales pour le filtrage
    for doc in docs:
        doc.meta = {
            "file_name": file_name,
            "cellule": cellule_nom
        }
        
    # 3. Découpage en morceaux (chunks)
    chunks = splitter.run(documents=docs)["documents"]
    
    # 4. Pipeline d'indexation vectorielle
    indexing_pipeline = Pipeline()
    
    # NOUVEAU : Embedder de documents connecté au serveur 800 (Nomic)
    indexing_pipeline.add_component("embedder", OpenAIDocumentEmbedder(
        api_key=Secret.from_token("EMPTY"),
        api_base_url="http://itgfrapapp800.prod.altengroup.dir:4200/v1",
        model="nomic-embed-text:latest"
    ))
    
    indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store, policy=DuplicatePolicy.OVERWRITE))
    
    indexing_pipeline.connect("embedder", "writer")
    
    # Lancement de l'indexation
    indexing_pipeline.run({"embedder": {"documents": chunks}})




def generer_plan_lms_json(liste_fichiers_autorises, document_store, llm):
    """
    Récupère tous les chunks des documents autorisés, les trie, 
    et génère un plan de formation LMS au format JSON strict.
    """
    # 1. Le "Retrieval" modifié pour le Stuffing
    # On utilise un filtre dynamique basé sur les fichiers autorisés pour l'utilisateur
    dynamic_filter = {"field": "meta.file_name", "operator": "in", "value": liste_fichiers_autorises}
    
    # On récupère TOUS les documents (Stuffing)
    docs_autorises = document_store.filter_documents(filters=dynamic_filter)
    
    # 2. Le double tri chronologique indispensable
    docs_tries = sorted(docs_autorises, key=lambda d: (d.meta.get("file_name", ""), d.meta.get("chunk_index", 0)))
    document_store = get_document_store()  # Assure-toi que c'est la même instance que celle utilisée pour l'indexation
    llm = get_llm()  # Assure-toi que c'est la même instance que celle utilisée pour le RAG

    # 3. Le Prompt Universel (Zéro Overfitting) avec le schéma exact validé
    prompt_template = """
    Tu es un Expert en Ingénierie Pédagogique et conception e-learning (LMS).
    Ton objectif est de transformer les documents de référence fournis en un parcours de formation modulaire.

    CONSIGNES STRICTES :
    1. Structure figée : Tu DOIS utiliser EXACTEMENT les clés JSON fournies ci-dessous.
    2. Valeurs dynamiques : Tu dois déduire toutes les valeurs à partir des documents.
    3. Anti-Paresse : Tu as l'interdiction d'utiliser des commentaires (//) ou des points de suspension (...). Tu es OBLIGÉ de générer l'intégralité du code JSON, ligne par ligne.

    Tu DOIS répondre UNIQUEMENT avec un objet JSON valide respectant cette structure exacte :
    {
      "analyse_preliminaire": {
        "themes_majeurs_identifies": ["Thème 1", "Thème 2"],
        "justification_pedagogique": "Bref résumé"
      },
      "schema_version": "1.0",
      "type": "lms_training_plan",
      "language": "Code langue",
      "title": "Titre global",
      "context": {
        "delivery_mode": "Déduit",
        "target_audience": ["Public 1"],
        "global_objective": "Objectif principal",
        "estimated_total_duration_hours": "Nombre entier",
        "recommended_calendar": "Recommandation"
      },
      "source_documents": ["Noms des fichiers lus"],
      "lms_configuration": {
        "course_format": "ex: modulaire",
        "access_mode": "ex: asynchrone",
        "tracking": {
          "completion_required": true,
          "completion_rule": "Règle déduite",
          "recommended_standards": ["SCORM 1.2"],
          "data_to_track": ["temps passé"]
        },
        "learner_support": ["Support 1"],
        "accessibility_and_usability": ["Règle 1"]
      },
      "course_structure": [
        {
          "module_id": "M1",
          "title": "Titre",
          "duration_minutes": "Nombre entier",
          "order": 1,
          "learning_objectives": ["Objectif 1"],
          "prerequisites": ["Prérequis"],
          "lms_units": [
            {
              "unit_id": "M1-L1",
              "title": "Titre",
              "type": "Type (video, interactive_page, quiz)",
              "duration_minutes": "Nombre",
              "completion": "ex: viewed, score_minimum_80"
            }
          ],
          "deliverable": "Livrable",
          "assessment": {
            "type": "Type",
            "passing_score_percent": 80,
            "attempts_allowed": 3,
            "manual_review_required": false,
            "reviewer_role": "Rôle",
            "remediation": "Action",
            "criteria": ["Critère"]
          }
        }
      ],
      "global_completion_rules": {
        "required_modules": ["M1"],
        "minimum_quiz_score_percent": 80,
        "assignments_required": true,
        "manual_validation_required": false,
        "certificate_enabled": true,
        "certificate_title": "Titre du certificat"
      },
      "recommended_lms_tags": ["tag1"]
    }

    Voici les documents de référence :
    {% for doc in documents %}
    --- Début du segment (Fichier: {{ doc.meta.file_name }}) ---
    {{ doc.content }}
    --- Fin du segment ---
    {% endfor %}
    """

    # 4. Construction et Exécution
    generation_pipeline = Pipeline()
    generation_pipeline.add_component("prompt_builder", PromptBuilder(template=prompt_template))
    generation_pipeline.add_component("llm", llm) 
    generation_pipeline.connect("prompt_builder", "llm")

    result = generation_pipeline.run({"prompt_builder": {"documents": docs_tries}})
    reponse_brute = result["llm"]["replies"] if isinstance(result["llm"]["replies"], list) else result["llm"]["replies"]

    # 5. Nettoyage et extraction du JSON validé
    match = re.search(r'\{.*\}', reponse_brute, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0)) # Retourne un dictionnaire Python valide
        except json.JSONDecodeError as e:
            return {"erreur": f"Erreur de syntaxe JSON : {str(e)}", "brut": reponse_brute}
    else:
        return {"erreur": "Aucun JSON trouvé dans la réponse.", "brut": reponse_brute}