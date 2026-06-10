Assistant & Plan LMS
Assistant & Plan LMS
ProgrammingError: can't adapt type 'dict'
Traceback:

File "C:\Users\mmimouni\AppData\Local\anaconda3\envs\alten_rag\lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 88, in exec_func_with_error_handling
    result = func()
File "C:\Users\mmimouni\AppData\Local\anaconda3\envs\alten_rag\lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 579, in code_to_exec
    exec(code, module.__dict__)
File "C:\Users\mmimouni\Desktop\PFE\SprintOne\SprintOneAlten\app.py", line 43, in <module>
    render_user() # <-- La vue s'affiche ici !
File "C:\Users\mmimouni\Desktop\PFE\SprintOne\SprintOneAlten\views\user_view.py", line 59, in render_user
    liste_fichiers_autorises = get_user_rag_perimeter(st.session_state.user)
File "C:\Users\mmimouni\Desktop\PFE\SprintOne\SprintOneAlten\views\user_view.py", line 14, in get_user_rag_perimeter
    cur.execute("SELECT u.role, u.niveau, u.cellule_id, c.nom FROM users u JOIN cellules c ON u.cellule_id = c.id WHERE u.id = %s", (user_id,))
