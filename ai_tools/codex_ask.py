# codex_ask.py

import argparse
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def ask_codex(prompt, model="gpt-4o-mini", temperature=0.2):
    print("⏳ Sending request to Codex...\n")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior Python developer and stock trading strategist. Give code when relevant."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=1500,
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask Codex to improve or generate Python trading code.")
    parser.add_argument("prompt", type=str, help="The prompt to send to Codex (in quotes)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Model to use (default: gpt-4o-mini)")
    args = parser.parse_args()

    output = ask_codex(args.prompt, args.model)
    print("📦 Codex Response:\n")
    print(output)
