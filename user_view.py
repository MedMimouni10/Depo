def render_user():
    # MOCK DE SÉCURITÉ À AJOUTER ICI :
    if "user" not in st.session_state:
        st.session_state.user = {
            "nom": "Alice", 
            "role": "Intégrant", 
            "niveau": "Débutant",
            "cellule": "Cellule Data"
        }
        
    # Suite de ton code normal...
    st.title("Assistant & Plan LMS")
