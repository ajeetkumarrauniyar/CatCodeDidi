import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name = "gemini-3-flash-preview",
    generation_config=generation_config,
)

chat_session = model.start_chat(
    history=[
    ]
)



def ask_gemini(user_input):
    # Send a message to Gemini and return the response text
    response = chat_session.send_message(user_input)
    return response.text