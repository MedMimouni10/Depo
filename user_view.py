# views/user_view.py
import streamlit as st
from repository.database import get_db_connection
from services.learning_service import get_parcours_user
from services.rag_service import generer_reponse_rag
import json
from services.rag_service import generer_plan_lms_json 


def get_user_rag_perimeter(user_id):
    """Récupère la liste des documents autorisés depuis PostgreSQL (Sprint 1)"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT u.role, u.niveau, u.cellule_id, c.nom FROM users u JOIN cellules c ON u.cellule_id = c.id WHERE u.id = %s", (user_id,))
    u_role, u_niveau, u_cellule_id, c_nom = cur.fetchone()
    
    cur.execute("SELECT document_id, override_type FROM user_document_overrides WHERE user_id = %s", (user_id,))
    overrides = {doc_id: o_type for doc_id, o_type in cur.fetchall()}
    
# Dans views/user_view.py
    cur.execute("SELECT id, file_name, target_roles, target_levels, skills, priority, sommaire FROM documents WHERE cellule_id = %s", (u_cellule_id,))
    docs_cellule = cur.fetchall()
    conn.close()
    
    docs_autorises = []
    for doc_id, file_name, t_roles, t_levels, skills, priority, sommaire in docs_cellule:
        match_auto = (u_role in t_roles) and (u_niveau in t_levels)
        statut_override = overrides.get(doc_id)
        if statut_override == 'FORCE_ADD' or (match_auto and statut_override != 'FORCE_REMOVE'):
            docs_autorises.append({
                "id": doc_id, 
                "name": file_name, 
                "skills": ", ".join(skills) if skills else "Général",
                "sommaire": sommaire # On ajoute le sommaire au dictionnaire
            })
            
    return {"cellule": c_nom, "role": u_role, "niveau": u_niveau, "documents": docs_autorises}

def render_user():



    """Interface Utilisateur avec Chat RAG Dynamique"""

    st.title("Assistant & Plan LMS")
    
    # Récupération de la liste des fichiers autorisés selon le profil de l'utilisateur
    liste_fichiers_autorises = get_user_rag_perimeter(st.session_state.user)
    
    # ---------------------------------------------------------
    # NOUVELLE SECTION : GÉNÉRATION DU PLAN LMS
    # ---------------------------------------------------------
    st.sidebar.header("🛠️ Outils Pédagogiques")
    st.sidebar.write(f"Documents accessibles : {len(liste_fichiers_autorises)}")
    
    if st.sidebar.button("🚀 Générer le Plan d'Onboarding LMS (JSON)"):
        if not liste_fichiers_autorises:
            st.sidebar.warning("Vous n'avez accès à aucun document.")
        else:
            with st.spinner("Générations du plan LMS en cours (analyse des documents... veuillez patienter)..."):
                
                # Appel à la logique métier (Pense à passer tes instances document_store et llm)
                resultat_json = generer_plan_lms_json(
                    liste_fichiers_autorises
                )
                
                if "erreur" in resultat_json:
                    st.error("Une erreur est survenue lors de la génération.")
                    st.code(resultat_json.get("brut", "Pas de détails"), language="text")
                else:
                    st.success("Plan LMS généré avec succès !")
                    
                    # Affichage interactif du JSON dans Streamlit
                    st.json(resultat_json, expanded=False)
                    
                    # Bouton pour télécharger le fichier physique
                    json_string = json.dumps(resultat_json, indent=4, ensure_ascii=False)
                    st.download_button(
                        label="💾 Télécharger le fichier .json",
                        file_name="plan_onboarding_lms.json",
                        mime="application/json",
                        data=json_string
                    )
    
    # 1. Initialisation de l'historique de chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 2. Récupération dynamique des droits d'accès
    profil_rag = get_user_rag_perimeter(st.session_state.id_utilisateur)
    liste_noms_fichiers = [doc['name'] for doc in profil_rag['documents']]
    
    # --- BARRE LATÉRALE : Affichage du profil et des Sommaires ---
    with st.sidebar:
        st.markdown("### 👤 Mon Profil")
        st.info(f"📍 {profil_rag['cellule']}\n\n💼 {profil_rag['role']}\n\n📈 {profil_rag['niveau']}")
        
        st.markdown("### 📑 Sommaires de mes documents")
        if not profil_rag['documents']:
            st.warning("Aucun document accessible.")
        else:
            for doc in profil_rag['documents']:
                with st.expander(f"📄 {doc['name']}"):
                    if doc['sommaire']:
                        st.markdown(doc['sommaire'])
                    else:
                        st.caption("Sommaire en cours d'analyse...")
        
        st.markdown("---")
        if st.button("🗑️ Vider l'historique du chat"):
            st.session_state.messages = []
            st.rerun()

    # --- ZONE PRINCIPALE : Le Chatbot ---
    st.title("💬 Assistant ALTEN (RAG)")
    st.caption("Posez vos questions, l'IA cherchera les réponses dans vos documents autorisés.")
    # ... (le reste du code du chatbot reste inchangé)
    
    from services.learning_service import generer_parcours_llm, sauvegarder_parcours, get_parcours_user
    # =============================
    # 🎓 Génération de formation
    # =============================
    st.markdown("## 🎓 Mon Parcours de Formation")

    parcours_existant = get_parcours_user(st.session_state.id_utilisateur)

    if parcours_existant:
        with st.expander("📚 Voir mon parcours généré"):
            st.json(parcours_existant)

    if st.button("🚀 Générer mon parcours personnalisé"):
        with st.spinner("Génération en cours..."):
            parcours = generer_parcours_llm(profil_rag)
            
            if "error" not in parcours:
                sauvegarder_parcours(st.session_state.id_utilisateur, parcours)
                st.success("✅ Parcours généré !")
                st.rerun()
            else:
                st.error(f"Erreur : {parcours['error']}")

    # Affichage de l'historique
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                with st.expander("🔍 Voir les sources"):
                    for i, source in enumerate(message["sources"]):
                        st.markdown(f"**Source {i+1} : {source.meta.get('file_name', 'Inconnu')}**")
                        st.caption(f"_{source.content[:200]}..._")

    # Champ de saisie pour l'utilisateur
    if prompt := st.chat_input("Posez votre question ici..."):
        
        # Afficher la question de l'utilisateur
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Générer et afficher la réponse de Mistral
        with st.chat_message("assistant"):
            with st.spinner("Gemma analyse vos documents..."):
                # C'est ici qu'on appelle notre service IA avec la liste stricte !
                reponse, sources = generer_reponse_rag(prompt, liste_noms_fichiers)
                
                st.markdown(reponse)
                
                if sources:
                    with st.expander("🔍 Voir les sources"):
                        for i, source in enumerate(sources):
                            st.markdown(f"**Source {i+1} : {source.meta.get('file_name', 'Inconnu')}**")
                            st.caption(f"_{source.content[:200]}..._")
                            
        # Sauvegarder la réponse dans l'historique
        st.session_state.messages.append({"role": "assistant", "content": reponse, "sources": sources})



