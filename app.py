from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from functions import *
import json
from bson import ObjectId
from datetime import datetime
from math import ceil
from datetime import datetime


# Helper function to convert ObjectId instances to strings
def convert_objectids(data):
    if isinstance(data, list):
        return [convert_objectids(item) for item in data]
    elif isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                new_data[key] = str(value)
            elif isinstance(value, (dict, list)):
                new_data[key] = convert_objectids(value)
            else:
                new_data[key] = value
        return new_data
    else:
        return data

# Initialize AI Model
gemini = create_model()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a strong secret key

# Connect to MongoDB
client = MongoClient('mongodb+srv://nanduedu655:o78agxf2PguYmVKS@attack.y5ncc.mongodb.net/')
db = client['cyberattack_db']
collection = db['c_attacks']  # Specify collection

# Make session variables available in all templates
@app.context_processor
def inject_session():
    return dict(session=session)

# Home Route
@app.route('/')
def home():
    return render_template('index.html')


@app.route("/get_statistics")
def get_statistics():
    # Count total documents
    total_reports = collection.count_documents({})

    # Count unique tactics and techniques
    tactics_set = set()
    techniques_set = set()

    for doc in collection.find({}, {"Tactics.id": 1, "Techniques.id": 1}):
        if "Tactics" in doc:
            for tactic in doc["Tactics"]:
                tactics_set.add(tactic["id"])
        if "Techniques" in doc:
            for technique in doc["Techniques"]:
                techniques_set.add(technique["id"])

    return jsonify({
        "total_reports": total_reports,
        "total_tactics": len(tactics_set),
        "total_techniques": len(techniques_set)
    })


@app.route('/get_trend_data')
def get_trend_data():
    reports = collection.find()
    trend_data = {}

    for report in reports:
        date = report.get('Date')
        if date:
            month_year = datetime.strptime(date, '%Y-%m-%d').strftime('%b %Y')
            trend_data[month_year] = trend_data.get(month_year, 0) + 1

    # Sort by month-year
    sorted_months = sorted(trend_data.keys(), key=lambda x: datetime.strptime(x, '%b %Y'))
    sorted_counts = [trend_data[month] for month in sorted_months]

    return jsonify({'months': sorted_months, 'counts': sorted_counts})




@app.route('/threats')
def threats():
    if 'username' not in session:
        return redirect(url_for('login'))

    per_page = 12
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', "").strip()
    selected_tactic = request.args.get('tactic', None)
    selected_technique = request.args.get('technique', None)
    selected_risk = request.args.get('risk', None)
    sort_order = request.args.get('sort', "desc")
    selected_year = request.args.get('year', None)  

    query = {}

    # Apply Search
    if search_query:
        query["$or"] = [
            {"Title": {"$regex": search_query, "$options": "i"}},
        ]

    # Apply Filters
    if selected_tactic:
        query["Tactics.name"] = selected_tactic
    if selected_technique:
        query["Techniques.name"] = selected_technique
    if selected_risk:
        query["Risk Factor"] = selected_risk
    if selected_year:
        query["Date"] = {"$regex": f"^{selected_year}"}

    # Sorting
    sort_option = [("Date", -1)] if sort_order == "desc" else [("Date", 1)]
    data = list(collection.find(query, {"_id": 0}).sort(sort_option))

    total_threats = len(data)
    total_pages = max(1, ceil(total_threats / per_page))
    threats_paginated = data[(page - 1) * per_page : page * per_page]

    # Extract Unique Filter Values
    all_tactics = sorted(set(tactic["name"] for threat in collection.find({}, {"Tactics": 1, "_id": 0}) 
                             for tactic in threat.get("Tactics", [])))
    all_techniques = sorted(set(tech["name"] for threat in collection.find({}, {"Techniques": 1, "_id": 0}) 
                                for tech in threat.get("Techniques", [])))
    all_risks = sorted(set(threat.get("Risk Factor") for threat in collection.find({}, {"Risk Factor": 1, "_id": 0}) 
                            if "Risk Factor" in threat))
    all_years = sorted(set(threat["Date"][:4] for threat in collection.find({}, {"Date": 1, "_id": 0}) if "Date" in threat), reverse=True)

    return render_template('threats.html', threats=threats_paginated, total_pages=total_pages, 
                           current_page=page, all_tactics=all_tactics, all_techniques=all_techniques, 
                           all_risks=all_risks, all_years=all_years, selected_tactic=selected_tactic, 
                           selected_technique=selected_technique, selected_risk=selected_risk, 
                           selected_year=selected_year, sort_order=sort_order, search_query=search_query)


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/team')
def team():
    return render_template('team.html')


# Upload Page (Only Admins)
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'role' not in session or session['role'] != 'admin':
        flash("Access Denied! Only admins can upload files.", "danger")
        return redirect(url_for('threats'))

    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file selected."}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected."}), 400

        # Extract text from PDF
        extracted_text = extract_text_from_pdf(file)
        if not extracted_text:
            return jsonify({"error": "Failed to extract text from PDF."}), 500

        # AI Analysis (Ensure the result is a Python dictionary or a list of dictionaries)
        json_response = generate_json(model=gemini, extracted_data=extracted_text)

        try:
            # If the AI analysis returns a string, convert it to a dict or list.
            if isinstance(json_response, str):
                json_response = json.loads(json_response)
            
            # Add the current system date to the document(s)
            current_date = datetime.now().strftime("%Y-%m-%d")
            # current_date = "2025-01-08"
            
            # Check if the response is a list
            if isinstance(json_response, list):
                if not json_response:
                    # Return an error response if no documents were generated.
                    return jsonify({"error": "No data extracted from PDF."}), 400
                if all(isinstance(doc, dict) for doc in json_response):
                    for doc in json_response:
                        doc["Date"] = current_date
                    # DO NOT insert into MongoDB here; data will be stored only after "Save Changes"
                    # collection.insert_many(json_response)
                else:
                    raise ValueError("Not all items in the JSON list are dictionaries.")
            elif isinstance(json_response, dict):
                json_response["Date"] = current_date
                # DO NOT insert into MongoDB here; data will be stored only after "Save Changes"
                # collection.insert_one(json_response)
            else:
                raise ValueError("AI response is neither a dictionary nor a list of dictionaries.")
            
            # Convert any ObjectId instances to strings before returning
            serializable_response = convert_objectids(json_response)
            return jsonify({"success": "Data successfully analyzed!", "data": serializable_response})
        except Exception as e:
            return jsonify({"error": f"Failed to process data: {str(e)}"}), 500

    return render_template('upload.html')

# Save Edited Analysis to MongoDB
@app.route('/save_analysis', methods=['POST'])
def save_analysis():
    if 'role' not in session or session['role'] != 'admin':
        return jsonify({"error": "Unauthorized access!"}), 403

    try:
        updated_data = request.json
        if not updated_data:
            return jsonify({"error": "No data provided"}), 400

        # Validate data structure
        def validate_document(doc):
            required_fields = ['Title', 'Risk Factor', 'Date']
            for field in required_fields:
                if field not in doc:
                    raise ValueError(f"Missing required field: {field}")
            return doc

        # Process documents
        if isinstance(updated_data, list):
            validated_data = [validate_document(doc) for doc in updated_data]
            result = collection.insert_many(validated_data)
            return jsonify({
                "success": f"Saved {len(result.inserted_ids)} reports",
                "inserted_ids": [str(id) for id in result.inserted_ids]
            })
        elif isinstance(updated_data, dict):
            validated_data = validate_document(updated_data)
            result = collection.insert_one(validated_data)
            return jsonify({
                "success": "Report saved successfully",
                "inserted_id": str(result.inserted_id)
            })
        else:
            raise ValueError("Invalid data format - must be list or dictionary")

    except ValueError as ve:
        return jsonify({"error": f"Validation error: {str(ve)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500



# Login Route
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
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
