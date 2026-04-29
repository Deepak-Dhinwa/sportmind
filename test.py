from llama_index.llms.google_genai import GoogleGenAI
import os
from dotenv import load_dotenv
load_dotenv()

for m in ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemma-4-27b-it", "gemma-3-27b-it"]:
    try:
        r = GoogleGenAI(model=m, api_key=os.getenv("GEMINI_API_KEY")).complete("hi")
        print(f"✓ {m}")
    except Exception as e:
        print(f"✗ {m}: {str(e)[:80]}")
