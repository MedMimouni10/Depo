Assistant & Plan LMS
KeyError: 'id'
Traceback:

File "C:\Users\mmimouni\AppData\Local\anaconda3\envs\alten_rag\lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 88, in exec_func_with_error_handling
    result = func()
File "C:\Users\mmimouni\AppData\Local\anaconda3\envs\alten_rag\lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 579, in code_to_exec
    exec(code, module.__dict__)
File "C:\Users\mmimouni\Desktop\PFE\SprintOne\SprintOneAlten\app.py", line 43, in <module>
    render_user() # <-- La vue s'affiche ici !
File "C:\Users\mmimouni\Desktop\PFE\SprintOne\SprintOneAlten\views\user_view.py", line 49, in render_user
    liste_fichiers_autorises = get_user_rag_perimeter(st.session_state.user["id"])
