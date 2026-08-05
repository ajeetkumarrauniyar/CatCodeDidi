import os
import time
import playsound3
import speech_recognition as sr
from gtts import gTTS
from AppOpener import open,close
import datetime

def bot_speak(text):
    tts = gTTS(text=text, lang="hi")
    filename = 'voice.mp3'
    tts.save(filename)
    playsound3.playsound(filename)

def voice_input():
    x = sr.Recognizer()
    with sr.Microphone() as source:
        print('\n Listening...')
        audio = x.listen(source)
        global said
        said = ""

        try:
            said = x.recognize_google(audio)
            print(said)
        except Exception as e:
            bot_speak('Maalik, Phir se boliye mai sun nahi paa rahi hu!')

    return said



def AppOpen(AppName):
    try:
        open(AppName, match_closest=True, throw_error=True)
        bot_speak(f'Thik hai Maalik! , Mai {AppName} ko open kar deti hu')
    except Exception as e:
        bot_speak(f'Maalik, {AppName} naam ka koi software hai hi nahi system mai!')

def ShutDownApp(AppName):
    try:
        close(AppName, match_closest=True)
        bot_speak(f'Maalik, {AppName} Ko Band Kar deti hu !')
    except Exception as e:
        bot_speak(f'Maalik, {AppName} naam ka koi software open nahi hai toh chinta mat kijiye')

# def ask_question(question):
#         try:
            
#         except Exception as e:
#             bot_speak("Maalik, mujhe iska answer nahi mil paya!")


moment = datetime.datetime.now()
current_time = int(moment.strftime("%H"))
if (current_time <= 5) :
    bot_speak(f'Good Morning Sir, Abhi Subah ke {current_time} baj rahe hai!')
elif(current_time == 12):
    bot_speak(f'Good Afternoon Sir, Abhi Dophar ke 12 baj rahe hai!')
elif(current_time <= 13):
    bot_speak(f'Good Afternoon Sir, Abhi Dophar ke {current_time-12} baj rahe hai!')
elif(current_time <= 17):
    bot_speak(f'Good Evening Sir, Abhi Shaam ke {current_time-12} baj rahe hai!')
else:
    bot_speak(f'Hello Night Owl, Abhi Raat ke {current_time-12} baj rahe hai !')



def father_queries():
    global father_related_question
    father_related_question = [
        "who is your father",
        'tere papa ka naam kya hai',
        'tumhare papa ka naam kya hai',
        'tumhare papa kaun hai',
        'tumhara developer kaun hai',
        'tumhen banaya kisne hai',
        "tumhen banaya"
    ]

father_queries()    


while True:

    voice_input()

    words = said
    list = words.split()
    print(list)


    if (said.lower() in father_related_question ):
        bot_speak('Mere Papa Anant Hai!')


    if list:

        if(list[0].lower() == 'shutdown'):
            bot_speak("Good Bye, Maalik!, Sulululu")
            break


        if len(list) > 1:
            
            if(list[0].lower() == "open"):
                AppName = "".join(list[1:])
                AppOpen(AppName)
            if(list[0].lower() == "close"):
                AppName = "".join(list[1:])
                ShutDownApp(AppName)



    
    # if words:
    #     ask_question(words)
            
    