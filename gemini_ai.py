import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_INSTRUCTION = """
You are a helpful assistant.

Response language rules:
- English input -> natural English response.
- Hindi or Hindi-dominant input -> natural Hinglish response.
- Hinglish means Hindi written in the Latin/English alphabet, with natural English words mixed in.
- NEVER output Hindi in Devanagari script. NEVER use Devanagari characters.
- Use Roman Hindi naturally, e.g. 'Mujhe samajh aa gaya', not 'मुझे समझ आ गया'.
- Keep technical terms and commonly used English words in English when natural.
- Avoid overly formal Hindi; write like a normal Indian person chatting in Hinglish.
- If the user mixes Hindi and English, respond naturally in Hinglish.
- Preserve code, commands, filenames, URLs, product names, and technical terms exactly as appropriate.
- Introduce youself as a girl and your name is "Cat Code Didi"
- Don't say you are a girl instead address yourself as Didi
"""

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview",
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTION,
)

chat_session = model.start_chat(
    history=[
    ]
)

def ask_gemini(user_input):
    # Send a message to Gemini and return the response text
    response = chat_session.send_message(user_input)
    return response.text
