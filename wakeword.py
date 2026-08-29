"""Local, offline wake-word detection.

Technology
----------
Vosk (Apache-2.0) running a *grammar-restricted* recogniser. The decoder is
given only the wake phrases plus "[unk]", so it is not transcribing arbitrary
speech - it is deciding which of four things it just heard. Measured on the
small en-us model: 74-141x realtime, i.e. roughly 1% of one core.

No audio ever leaves the machine. Gemini and the Google Web Speech API are
used only for a command the user has actually asked for.

Why not the alternatives:
- Streaming the mic to a cloud recogniser: explicitly ruled out, and would
  mean uploading everything said near the machine.
- Porcupine: excellent and cheap, but needs an account-bound access key and a
  per-platform .ppn built in a web console for a custom phrase.
- openWakeWord: MIT, but ships models for a fixed set of phrases; "Cat Code
  Didi" would have to be trained, and it pulls in onnxruntime.
- pocketsphinx: no maintained wheels for current Pythons; builds badly on
  Apple Silicon.

False positives
---------------
Grammar mode maps *every* utterance onto the nearest allowed phrase, so
"what is the weather today" decodes as "[unk] didi". A detection is therefore
only accepted when the decoded text is exactly a wake phrase - any "[unk]"
alongside it means the user was saying something else. Measured over the
three wake phrases and six negatives, this accepts all three and rejects all
six.

Microphone ownership
--------------------
The listener holds the mic only while actually listening. On a detection it
releases it *before* announcing the wake, so the command listener can take
over; the caller resumes it when the command is finished. One long-lived
thread, parked on an Event while paused - never a busy loop, never respawned.
"""

import json
import logging
import threading

import speech

log = logging.getLogger("catcodedidi")

WAKE_PHRASES = ("cat code didi", "cat code", "didi")

SAMPLE_RATE = 16000
BLOCK_FRAMES = 4000          # 0.25s per read - responsive without spinning


def is_available():
    """True when the wake-word engine can be imported."""
    import importlib.util
    try:
        return importlib.util.find_spec("vosk") is not None
    except Exception:
        return False


class WakeWordDetector:
    """Listens for a wake phrase and calls `on_wake` exactly once per hit.

    Lifecycle: start() -> (listening) -> wake -> paused -> resume() -> ...
    stop() ends the thread. All methods are safe to call from the UI thread;
    nothing here blocks it.
    """

    def __init__(self, on_wake, on_status=None, phrases=WAKE_PHRASES):
        self._on_wake = on_wake
        self._on_status = on_status or (lambda message: None)
        self._phrases = {p.lower() for p in phrases}
        self._thread = None
        self._stop = threading.Event()
        self._active = threading.Event()      # set == should be listening

    # -- control -------------------------------------------------------

    @property
    def listening(self):
        return self._active.is_set() and not self._stop.is_set()

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        """Begin listening. Loading the model happens on the worker thread, so
        the first call returns immediately even though it may download."""
        if self.running:
            self._active.set()
            return
        self._stop.clear()
        self._active.set()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="wake-word")
        self._thread.start()

    def pause(self):
        """Stop listening and release the microphone; keep the thread warm."""
        self._active.clear()

    def resume(self):
        if self.running:
            self._active.set()
        else:
            self.start()

    def stop(self):
        self._stop.set()
        self._active.clear()

    # -- worker --------------------------------------------------------

    def _load(self):
        import vosk
        vosk.SetLogLevel(-1)
        self._on_status("Preparing wake word…")
        model = vosk.Model(lang="en-us")      # cached in ~/.cache/vosk
        grammar = json.dumps(sorted(self._phrases) + ["[unk]"])
        return vosk, model, grammar

    def _recognizer(self, vosk, model, grammar):
        return vosk.KaldiRecognizer(model, SAMPLE_RATE, grammar)

    def _run(self):
        try:
            vosk, model, grammar = self._load()
        except Exception as error:
            log.warning("Wake word unavailable (%s)", type(error).__name__)
            self._on_status(f"Wake word unavailable ({type(error).__name__})")
            self._active.clear()
            return

        self._on_status("ready")
        while not self._stop.is_set():
            # Parks the thread while paused - no polling, no CPU.
            if not self._active.wait(timeout=0.25):
                continue
            try:
                self._listen_once(vosk, model, grammar)
            except speech.MicrophoneBusy:
                # Someone else legitimately has the mic; wait and retry.
                self._stop.wait(0.5)
            except Exception as error:
                log.warning("Wake listener stopped (%s)", type(error).__name__)
                self._on_status(f"Wake word stopped ({type(error).__name__})")
                self._active.clear()

    def _listen_once(self, vosk, model, grammar):
        """Hold the mic and decode until a wake phrase lands or we are paused."""
        import pyaudio

        recognizer = self._recognizer(vosk, model, grammar)
        audio = pyaudio.PyAudio()
        detected = False
        with speech.microphone.claim("wake listener"):
            stream = None
            try:
                stream = audio.open(format=pyaudio.paInt16, channels=1,
                                    rate=SAMPLE_RATE, input=True,
                                    frames_per_buffer=BLOCK_FRAMES)
                while self._active.is_set() and not self._stop.is_set():
                    data = stream.read(BLOCK_FRAMES, exception_on_overflow=False)
                    if not recognizer.AcceptWaveform(data):
                        continue
                    if self._is_wake(json.loads(recognizer.Result())):
                        # Release the mic before telling anyone, so the command
                        # listener never races us for it.
                        detected = True
                        self._active.clear()
                        break
            finally:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
                audio.terminate()

        # Only a real detection wakes the assistant - a pause() must not.
        if detected and not self._stop.is_set():
            self._fire()

    def _is_wake(self, result):
        """Accept only an exact wake phrase - see the false-positive note."""
        text = (result.get("text") or "").strip().lower()
        if text in self._phrases:
            log.info("Wake word detected: %r", text)
            return True
        return False

    def _fire(self):
        try:
            self._on_wake()
        except Exception as error:
            log.warning("Wake callback failed (%s)", type(error).__name__)
