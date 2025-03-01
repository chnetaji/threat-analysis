from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
from pymongo import MongoClient
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'ASBVHGTGHKJBKJGHUNKJGUBJH$%^##JHVBJHF'  # Replace with a strong secret key

# Connect to MongoDB
client = MongoClient('mongodb+srv://nanduedu655:o78agxf2PguYmVKS@attack.y5ncc.mongodb.net/')
db = client['cyberattack_db']

@app.context_processor
def inject_session():
    return dict(session=session)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or 'role' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('threats'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        password = request.form.get('password')

        if role not in ['admin', 'user']:
            flash("Invalid role selected.", "danger")
            return redirect(url_for('login'))

        user = db[role].find_one({"email": email, "password": password})

        if user:
            session['username'] = email
            session['role'] = role
            flash("Login successful!", "success")
            return redirect(url_for('threats'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/threats')
@login_required
def threats():
    return render_template('threats.html')

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload():
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
