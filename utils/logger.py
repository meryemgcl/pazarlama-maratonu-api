"""
utils/logger.py — Merkezi, yapılandırılmış loglama modülü.
Her servis bu modülü kullanır; hiçbir hata sessizce kaybolmaz.
"""
import logging
import sys
from datetime import datetime, timezone


class RenkliFormatter(logging.Formatter):
    """Terminal'de renkli log çıktısı."""
    RENKLER = {
        logging.DEBUG:    "\033[36m",   # Cyan
        logging.INFO:     "\033[32m",   # Yeşil
        logging.WARNING:  "\033[33m",   # Sarı
        logging.ERROR:    "\033[31m",   # Kırmızı
        logging.CRITICAL: "\033[35m",   # Mor
    }
    SIFIRLA = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        renk = self.RENKLER.get(record.levelno, "")
        zaman = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"{renk}[{zaman}] [{record.levelname:<8}] "
            f"[{record.name}] {record.getMessage()}{self.SIFIRLA}"
        )


def get_logger(name: str) -> logging.Logger:
    """
    İsimlendirilmiş logger döner.
    Kullanım: logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(RenkliFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    return logger
