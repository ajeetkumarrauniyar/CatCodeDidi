"""Application startup and command routing."""

if __package__:
    from .commands import handle_close_command, handle_open_command, is_father_query
    from .personality import greet_user
    from .speech import bot_speak, voice_input
else:
    from commands import handle_close_command, handle_open_command, is_father_query
    from personality import greet_user
    from speech import bot_speak, voice_input


def main():
    """Start the assistant and continue listening for commands."""
    greet_user()
    while True:
        said = voice_input()
        command_words = said.split()
        print(command_words)

        if is_father_query(said):
            bot_speak("Mere Papa Anant Hai!")

        if command_words:
            if command_words[0].lower() == "shutdown":
                bot_speak("Good Bye, Maalik!, Sulululu")
                break
            if len(command_words) > 1:
                app_name = " ".join(command_words[1:])
                if command_words[0].lower() == "open":
                    handle_open_command(app_name)
                if command_words[0].lower() == "close":
                    handle_close_command(app_name)


if __name__ == "__main__":
    main()