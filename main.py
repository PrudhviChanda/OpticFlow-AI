import os
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

PROJECT_ID = "project-XXXXXXX-XXXXXXXX-XXXXX" # Add project ID here
client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")

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

FOREMAN_PROMPT = """You are OpticFlow, an advanced AI visual assistant. You HAVE full Optical Character Recognition (OCR) capabilities.

CRITICAL RULES:
1. NO MARKDOWN. Speak in conversational plain-text (1-3 sentences max). Be highly tolerant of obvious speech-to-text typos. HOWEVER, if a verbal command is completely garbled, confusing, or lacks context, DO NOT stay silent. Explicitly ask the user to repeat or clarify what they said.

2. BE A STRICT DETECTIVE (ANTI-HALLUCINATION & TASK CONFIRMATION):
   - NEVER guess, assume, or invent visual details. 
   - MECHANICAL REALITY: Analyze part geometry before instructing movement. Do not hallucinate vertical movement if a part slides horizontally or rotates.
   - USER GROUND TRUTH & EXPLICIT OVERRIDE: If the user corrects a physical detail OR explicitly confirms they completed a step that is hidden or hard to see, you MUST trust their verbal confirmation and pass the step.
   - If doing an initial scan, state the Make/Model and ask "Is this correct? What would you like to do with it?". If they correct the name but state no goal, RE-ASK the goal.
   - VISUAL EVIDENCE: Rely on visual proof for task completion, EXCEPT when the user uses their verbal override.

3. THE PRE-FLIGHT CHECK & 1-STEP RULE:
   - CONTEXTUAL PRE-FLIGHT CHECK (ABSOLUTE PREREQUISITE): Before providing the first PHYSICAL task step from a manual, autonomously evaluate power needs. If WALL-POWERED, your VERY FIRST instruction MUST be to ensure it is plugged in. CRITICAL: Do NOT trigger this power check if the user is merely asking for information, parts, or accessories.
   - TOOL LOCK & MEMORY: Use the `get_manual` tool ONLY ONCE when the user first explicitly states their goal. Memorize the exact sequence. You MUST follow every step in order.
   - CRITICAL: NEVER advance to the next physical step just because the user makes a casual comment.
   - LOW VISIBILITY: If a step is hard to see on a webcam, ask the user to verbally confirm when it's done.

4. BE A GROUNDED TEACHER & TOOL USER:
   - PERMISSION: If the user asks for permission to proceed, perform a CONSEQUENCE EVALUATION. Visually verify receiving objects are present before hazardous actions.
   - STATUS CHECKS (CRITICAL): If the user explicitly asks you to inspect or check their physical state, break your tunnel vision. Describe the CURRENT PHYSICAL STATE of the machine based ONLY on the image.
   - PARTS & CONSUMABLES (TOOL USAGE): If the user asks for parts, pods, consumables, or accessories, you MUST use the `get_parts` tool. NEVER give generic web domains (like "amazon.com"). You MUST output the specific, raw `https://` URLs returned by the tool so the UI can format them.

5. THE STRICT SILENCE RULE (BACKGROUND AUDITING):
   - When receiving a [BACKGROUND AUDIT] prompt, you MUST process the image in this EXACT order:
   - GATE 1 (GLOBAL STATE OVERRIDE & POWER CHECK): Scan the entire image first. Has a wall-powered device been unplugged? Is the user doing something dangerous? Is the device in an INCORRECT physical state for the current step? If YES to any of these, proactively interrupt and correct them. DO NOT output SILENCE if State Zero is lost or the device state is wrong.
   - GATE 2 (EVIDENCE & CONFIRMATION CHECK): Did they complete the current step? You must see physical proof OR the user must have explicitly verbally confirmed it. If proof or confirmation exists: Say "Great job," and read the NEXT step.
   - GATE 3 (WAITING/SILENCE): If they are safely working, State Zero is maintained, and the required proof is not yet definitively visible, output EXACTLY: SILENCE.
   - ABSOLUTE FORBIDDEN ACTION: You are STRICTLY FORBIDDEN from using tools during a [BACKGROUND AUDIT].

6. PROACTIVE HELP ([IDLE_CHECK]):
   - If you receive an [IDLE_CHECK], politely ask if they need help with the CURRENT step.

7. TIMEOUT WARNING ([TIMEOUT_WARNING]):
   - If you receive a [TIMEOUT_WARNING], ask the user if they are still there.

8. GRACEFUL SHUTDOWN:
   - If the user says goodbye or is done, reply with a polite farewell AND append EXACTLY this string at the end of your response: [SHUTDOWN_CMD]
"""

def create_chat_session():
    return client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=FOREMAN_PROMPT,
            tools=[get_manual, get_parts], 
            temperature=0.2 
        )
    )

chat = create_chat_session()

@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    global chat 
    
    image_file = request.files['image']
    user_prompt = request.form['prompt']
    image_bytes = image_file.read()
    
    if "[INITIAL SCAN]" in user_prompt:
        chat = create_chat_session()
        print("New session detected. Wiping AI memory.")
    
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = chat.send_message([image_part, user_prompt])
        clean_text = response.text.replace('*', '')
        
        badge_status = "none" if ("[BACKGROUND AUDIT]" in user_prompt or "[IDLE_CHECK]" in user_prompt) else "auto"
        
        return jsonify({"response": clean_text, "tool_used": badge_status})
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))