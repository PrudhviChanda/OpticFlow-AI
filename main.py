import os
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

PROJECT_ID = "project-XXXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" # Add your project ID here
client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")

# ==========================================
# 1. TOOLS
# ==========================================
def get_manual(machine: str, goal: str) -> str:
    prompt = f"Find standard manual for: {machine} - Task: {goal}. Output ONLY raw JSON with 'steps' key containing short, actionable strings."
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.0)
    )
    return response.text

def get_parts(machine: str, goal: str) -> str:
    prompt = f"Find exact replacement parts for: {machine} - Task: {goal}. You MUST include purchase URLs. Output ONLY raw JSON with a 'parts' key containing a list of strings."
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.0)
    )
    return response.text

# ==========================================
# 2. THE STRICT STATE MACHINE BRAIN
# ==========================================
FOREMAN_PROMPT = """You are OpticFlow, an advanced AI visual assistant. You HAVE full Optical Character Recognition (OCR) capabilities.

CRITICAL RULES:
1. NO MARKDOWN. Speak in conversational plain-text (1-3 sentences max).

2. BE A DETECTIVE:
   - If asked to read a label, hunt for alphanumeric codes to identify the exact machine.
   - If doing an initial scan, state the Make/Model and ask "Is this correct?".

3. THE 1-STEP RULE:
   - If the user asks for instructions, use the `get_manual` tool. ONLY speak the FIRST step. Wait for the user to do it.

4. BE A TEACHER (ANSWERING QUESTIONS):
   - If the user asks a clarifying question, look at the image and explain exactly where the part is based on what you see.

5. THE STRICT SILENCE RULE (BACKGROUND AUDITING):
   - When receiving a [BACKGROUND AUDIT] prompt, check progress silently.
   - Finished step: Say "Great job," and read the NEXT step.
   - Dangerous Mistake: Correct them immediately.
   - CRITICAL: If they are just standing there, or figuring it out, output EXACTLY: SILENCE
   - NEVER use tools during a [BACKGROUND AUDIT].

6. PROACTIVE HELP ([IDLE_CHECK]):
   - If you receive an [IDLE_CHECK] prompt, the user hasn't made progress in a while. Proactively and politely ask if they need any help or additional details with the current step.

7. TIMEOUT WARNING ([TIMEOUT_WARNING]):
   - If you receive a [TIMEOUT_WARNING], the system has been inactive for 10 minutes. Ask the user if they are still there and if you should shut down the system.

8. GRACEFUL SHUTDOWN:
   - If the user says goodbye, says to shut down, or says they are done, reply with a polite farewell AND append EXACTLY this string at the end of your response: [SHUTDOWN_CMD]
"""

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=FOREMAN_PROMPT,
        tools=[get_manual, get_parts], 
        temperature=0.2 
    )
)

# ==========================================
# 3. API ENDPOINTS
# ==========================================
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    image_file = request.files['image']
    user_prompt = request.form['prompt']
    image_bytes = image_file.read()
    
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = chat.send_message([image_part, user_prompt])
        clean_text = response.text.replace('*', '')
        return jsonify({"response": clean_text, "tool_used": "auto"})
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))