"""
Language Detector — uses langdetect (Google's CLD2-based detection).
Supports 55 languages. Deterministic results.

Returns language code + confidence score.
Detects mixed-language documents.
"""
import logging

logger = logging.getLogger(__name__)

NAMES = {
    "fr": "French", "en": "English", "ar": "Arabic", "de": "German",
    "es": "Spanish", "it": "Italian", "pt": "Portuguese", "nl": "Dutch",
    "ru": "Russian", "zh-cn": "Chinese", "ja": "Japanese", "ko": "Korean",
    "tr": "Turkish", "pl": "Polish", "sv": "Swedish", "da": "Danish",
    "no": "Norwegian", "fi": "Finnish", "cs": "Czech", "ro": "Romanian",
    "el": "Greek", "he": "Hebrew", "hi": "Hindi", "vi": "Vietnamese",
}


def detect_language(text: str) -> tuple[str, float]:
    if not text or len(text.strip()) < 20:
        return "unknown", 0.0

    try:
        from langdetect import detect_langs, DetectorFactory
        DetectorFactory.seed = 0  # deterministic

        results = detect_langs(text[:3000])
        if not results:
            return "unknown", 0.0

        lang = str(results[0].lang)
        conf = round(results[0].prob, 2)
        name = NAMES.get(lang, lang)

        logger.info(f"[LANGUAGE] {name} ({lang}) — {conf*100:.0f}%")

        if len(results) > 1 and results[1].prob > 0.2:
            second = NAMES.get(str(results[1].lang), str(results[1].lang))
            logger.info(f"[LANGUAGE] Also detected: {second} ({results[1].prob*100:.0f}%)")

        return lang, conf

    except ImportError:
        logger.warning("[LANGUAGE] langdetect not installed — pip install langdetect")
        return "unknown", 0.0
    except Exception as e:
        logger.warning(f"[LANGUAGE] Error: {e}")
        return "unknown", 0.0