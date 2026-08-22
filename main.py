"""Application startup and command routing."""

from commands import handle_close_command, handle_open_command, is_father_query, take_screenshot
from personality import greet_user
from speech import bot_speak, voice_input
from data import exit_commands
from gemini_ai import ask_gemini
from rich.console import Console
from rich.markdown import Markdown
import re

console = Console()

def main():
    """Start the assistant and continue listening for commands."""
    greet_user()


    while True:
        said = voice_input()
        command_words = said.split()

        if is_father_query(said):
            bot_speak("Mere Papa Anant Hai!")

        if command_words:
            said_lower = said.strip().lower()
            if said_lower in exit_commands:
                bot_speak("Good Bye, Maalik!, Sulululu")
                break
            if len(command_words) > 1:
                app_name = " ".join(command_words[1:])
                if command_words[0].lower() == "open":
                    handle_open_command(app_name)
                    continue # Skip AI code if this matches
                if command_words[0].lower() == "close":
                    handle_close_command(app_name)
                    continue # Skip AI code if this matches

            if "screenshot" in command_words:
                take_screenshot()
                continue  # Skip AI code if this matches

        if len(command_words) > 1:        
            try:
                ai_response = ask_gemini(said)
                console.print(Markdown(ai_response))
                clean_ai_response = re.sub(r'[*:;\/\\|]', '', ai_response)
                bot_speak(clean_ai_response)
            except Exception as error:
                bot_speak("Maalik, Mere System mein kuch dikkat aa rahi hai!")        
                print(f"Error: {error}")
if __name__ == "__main__":
    main()