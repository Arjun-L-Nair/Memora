"""
ml/emotion_classifier.py

Text-based emotion detection from student chat messages and reflection
text, for the learning companion (Mira) and EmotionLog.

Model provenance:
    A DistilBERT classifier fine-tuned on GoEmotions (Google, 58K
    Reddit comments, 28 emotions), remapped to 6 core emotions and
    exported to ONNX for CPU inference (see train_emotion_model.py in
    the project root for the exact training/export script used,
    including the label mapping table). Verified before being wired in
    here: confident (94-99%), well-separated probability outputs on a
    held-out sanity set — a genuine improvement over an earlier export
    attempt that turned out to be an untrained classifier head
    (near-uniform ~1/6 probabilities regardless of input).

Known accuracy limitation (be aware of this, not just decorative
disclaimer text): manual testing found the model reliably distinguishes
"confused" and "anxious" (95%+ confidence, consistently correct), but
sometimes confuses same-valence pairs — "happy" vs "calm", and
"frustrated" vs "sad" — since GoEmotions' underlying label clusters for
those pairs (e.g. joy/love/gratitude vs. approval/relief/neutral)
genuinely overlap in tone. This is a real model limitation, not a bug;
it still meaningfully outperforms the keyword-lexicon baseline it
replaced, which had no learned nuance at all.

Graceful degradation: if onnxruntime isn't installed, or the model
files under ml/emotion_model_onnx/ are missing/corrupted, this module
falls back automatically to the deterministic keyword-lexicon
classifier (LexiconEmotionClassifier) — Mira's emotion-aware behavior
degrades gracefully rather than crashing the app.

Six core emotions targeted (a deliberate narrowing of GoEmotions' 28,
chosen for relevance to ASD learners' expressed states): happy, calm,
frustrated, anxious, confused, sad.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("memora.ml.emotion_classifier")

CORE_EMOTIONS: list[str] = ["happy", "calm", "frustrated", "anxious", "confused", "sad"]

_ONNX_MODEL_DIR = Path(__file__).parent / "emotion_model_onnx"

# Small, documented keyword lexicon per core emotion — kept as the
# fallback classifier. Deliberately simple and inspectable; used only
# when the ONNX model can't be loaded (see _build_default_classifier).
_LEXICON: dict[str, list[str]] = {
    "frustrated": ["frustrated", "annoying", "annoyed", "hate this", "stupid", "ugh", "so hard", "give up", "can't do this"],
    "anxious": ["worried", "scared", "nervous", "anxious", "afraid", "what if", "panic", "overwhelmed"],
    "confused": ["confused", "confusing", "don't understand", "dont understand", "what does this mean", "lost", "huh", "unclear"],
    "sad": ["sad", "upset", "crying", "cry", "unhappy", "down today", "lonely"],
    "happy": ["happy", "great", "awesome", "love this", "fun", "excited", "yay", "cool"],
    "calm": ["okay", "fine", "ready", "calm", "good", "understood", "got it"],
}


class EmotionPrediction(BaseModel):
    emotion: str
    confidence: float


class EmotionClassifier(ABC):
    """Abstract interface so the lexicon baseline and the fine-tuned
    ONNX model are interchangeable to callers."""

    @abstractmethod
    def classify(self, text: str) -> EmotionPrediction: ...


class LexiconEmotionClassifier(EmotionClassifier):
    """
    Deterministic keyword-overlap classifier. Confidence is the
    fraction of matched-emotion keyword hits relative to total hits
    across all emotions found in the text; defaults to "calm" at low
    confidence when nothing matches (a neutral, non-alarming default
    is safer than guessing a distressed emotion from no evidence).
    """

    def classify(self, text: str) -> EmotionPrediction:
        normalized = text.lower()
        scores: dict[str, int] = {emotion: 0 for emotion in CORE_EMOTIONS}

        for emotion, keywords in _LEXICON.items():
            for keyword in keywords:
                if keyword in normalized:
                    scores[emotion] += 1

        total_hits = sum(scores.values())
        if total_hits == 0:
            return EmotionPrediction(emotion="calm", confidence=0.3)

        top_emotion = max(scores, key=lambda e: scores[e])
        confidence = scores[top_emotion] / total_hits
        return EmotionPrediction(emotion=top_emotion, confidence=round(confidence, 2))


class OnnxEmotionClassifier(EmotionClassifier):
    """
    Fine-tuned DistilBERT emotion classifier, running via onnxruntime
    for fast CPU inference (no GPU required in production). Loads the
    tokenizer + ONNX graph once at construction; raises on any failure
    so the caller (_build_default_classifier) can fall back to the
    lexicon classifier instead of leaving the app in a half-broken
    state.
    """

    def __init__(self, model_dir: Path = _ONNX_MODEL_DIR) -> None:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        if not (model_dir / "model.onnx").exists():
            raise FileNotFoundError(f"No model.onnx found under {model_dir}")

        self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self._session = ort.InferenceSession(
            str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"]
        )

        # id2label from the model's own config.json is the source of
        # truth for label order — NOT this module's CORE_EMOTIONS list
        # — so a mismatch between the two would be loud (a KeyError
        # below) rather than silently mislabeling every prediction.
        import json

        with open(model_dir / "config.json") as f:
            config = json.load(f)
        id2label = config.get("id2label", {})
        self._labels = [id2label[str(i)] for i in range(len(id2label))]

        mismatch = set(self._labels) - set(CORE_EMOTIONS)
        if mismatch:
            raise ValueError(
                f"Model's id2label contains unexpected emotion(s) not in "
                f"CORE_EMOTIONS: {mismatch}. Refusing to load a model whose "
                f"labels don't match this app's expected emotion set."
            )

    def classify(self, text: str) -> EmotionPrediction:
        import numpy as np

        inputs = self._tokenizer(text, return_tensors="np", truncation=True, max_length=128)
        outputs = self._session.run(
            None,
            {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64),
            },
        )
        logits = outputs[0][0]
        probs = np.exp(logits) / np.exp(logits).sum()
        predicted_index = int(np.argmax(probs))

        return EmotionPrediction(
            emotion=self._labels[predicted_index],
            confidence=round(float(probs[predicted_index]), 3),
        )


def _build_default_classifier() -> EmotionClassifier:
    """
    Try to load the fine-tuned ONNX model; fall back to the lexicon
    classifier on any failure (missing onnxruntime/transformers
    packages, missing model files, corrupted export, label mismatch).
    Logged clearly either way so it's obvious at startup which
    classifier is actually active.
    """
    try:
        classifier = OnnxEmotionClassifier()
        logger.info("Loaded fine-tuned ONNX emotion classifier from %s", _ONNX_MODEL_DIR)
        return classifier
    except Exception as exc:
        logger.warning(
            "Could not load ONNX emotion classifier (%s); falling back to "
            "the keyword-lexicon classifier. Emotion detection will still "
            "work, just with less nuance.",
            exc,
        )
        return LexiconEmotionClassifier()


_classifier: EmotionClassifier = _build_default_classifier()


def classify_emotion(text: str) -> EmotionPrediction:
    """Public entry point used by learning_companion_service.py."""
    return _classifier.classify(text)
