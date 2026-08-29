import datetime

import personality


class _FrozenDatetime(datetime.datetime):
    _hour = 9

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, cls._hour, 0, 0)


def _greeting_at(hour, monkeypatch):
    _FrozenDatetime._hour = hour
    monkeypatch.setattr(personality.datetime, "datetime", _FrozenDatetime)
    return personality.greeting()


def test_greeting_morning(monkeypatch):
    assert "Good Morning" in _greeting_at(8, monkeypatch)


def test_greeting_noon(monkeypatch):
    assert "Good Afternoon" in _greeting_at(12, monkeypatch)


def test_greeting_afternoon(monkeypatch):
    assert "Good Afternoon" in _greeting_at(15, monkeypatch)


def test_greeting_evening(monkeypatch):
    assert "Good Evening" in _greeting_at(19, monkeypatch)


def test_greeting_night(monkeypatch):
    assert "Night Owl" in _greeting_at(2, monkeypatch)


def test_greeting_is_nonempty_string(monkeypatch):
    assert isinstance(_greeting_at(10, monkeypatch), str)
