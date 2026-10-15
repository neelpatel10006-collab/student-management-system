Student Management System with Analytics & ML Predictor
Python for Data Science (BE05000231) - PBL3 Mini Project
Features
Secure admin login (PBKDF2-SHA256 salted hashing)
Add / search / filter / sort / edit / delete students (SQLite)
Analytics dashboard: descriptive stats + interactive Plotly charts
Automatic grades (A+ to F), class rank, leaderboard and downloadable PDF report card
Export to CSV and Excel
Beyond-syllabus topics
Streamlit (web UI), Plotly, password hashing, PDF generation with fpdf2, Excel export via openpyxl.
Run
pip install -r requirements.txt
streamlit run app.py
Login: admin / admin123, then click "Load 60 sample students" in the sidebar.
