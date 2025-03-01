from dotenv import load_dotenv
import google.generativeai as genai
import pdfplumber
import os
import json

def create_model() -> genai.GenerativeModel:
    """Loads API key and initializes the Gemini AI model."""
    load_dotenv()
    SECRET_KEY = os.getenv("API_KEY")

    genai.configure(api_key=SECRET_KEY)
    return genai.GenerativeModel("gemini-1.5-flash")

def generate_json(model: genai.GenerativeModel, extracted_data: str):
    """Generates structured JSON output using AI."""
    prompt = f'''I will provide text extracted from a Cyber Threat Report. Generate a structured JSON output with **complete details**.

    **Extract ALL relevant information, including ATT&CK framework data. Ensure no fields are empty or null.**

    **Format the output as follows:**
    [
        {{
            "Title": "(Concise attack summary)",
            "Detailed Description": "(Complete technical details about the attack)",
            "Attack_type": "(Type of attack as per ATT&CK framework)",
            "Tactics": [
                {{"name": "(Tactic Name)", "id": "(MITRE ATT&CK ID)"}}
            ],
            "Techniques": [
                {{"name": "(Technique Name)", "id": "(MITRE ATT&CK ID)"}}
            ],
            "Risk Factor": "(High/Medium/Low based on severity)",
            "Key Points": [
                "(Extract main attack characteristics)",
                "(Summarize key findings)"
            ],
            "Mitigations": [
                "(Recommended defensive strategies)",
                "(Possible countermeasures)"
            ]
        }}
    ]

    **Important Instructions:**
    - **Extract all attacks separately** (If multiple attacks are mentioned, return them as an **array**).
    - Extract **ATT&CK Tactics & Techniques with their correct IDs**.
    - Ensure **Key Points & Mitigations are always present**.
    - Output should be **STRICTLY in JSON format** with **NO missing fields**.

    **Extracted Report Text:**
    {extracted_data}
    '''
    try:
        response = model.generate_content(prompt)
        json_response = format_json(response.text)

        # Ensure it's always a list of attacks
        if isinstance(json_response, dict):
            json_response = [json_response]

        # Ensure no missing fields & handle nulls
        for attack in json_response:
            attack["Tactics"] = attack.get("Tactics", [])
            attack["Techniques"] = attack.get("Techniques", [])
            attack["Key Points"] = attack.get("Key Points", ["No key points available"])
            attack["Mitigations"] = attack.get("Mitigations", ["No mitigation strategies provided"])

        return json_response

    except Exception as e:
        return {"error": str(e)}

def extract_text_from_pdf(file):
    """Extracts text from uploaded PDF file."""
    if file.filename.endswith('.pdf'):
        with pdfplumber.open(file) as pdf:
            return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    return None

def format_json(response: str):
    """Formats AI response for frontend display."""
    try:
        response = response.strip().removeprefix("```json").removesuffix("```")
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format"}