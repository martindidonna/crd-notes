from __future__ import annotations


class CrdNotesError(Exception):
    """Errore applicativo con messaggio presentabile all'utente."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ConfigurationError(CrdNotesError):
    pass


class ConversionError(CrdNotesError):
    pass


class TranscriptionError(CrdNotesError):
    pass


class AiConnectorError(CrdNotesError):
    pass


class LibraryError(CrdNotesError):
    pass
