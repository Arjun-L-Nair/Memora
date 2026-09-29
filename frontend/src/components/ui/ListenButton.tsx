import { useEffect, useRef, useState } from "react";
import { Volume2, Square } from "lucide-react";

import { Button } from "@/components/ui/Button";

/**
 * ListenButton — reads the given text aloud using the browser's
 * built-in SpeechSynthesis API (window.speechSynthesis). No backend
 * call, no API key, works fully offline once the page has loaded —
 * every evergreen desktop/mobile browser (Chrome, Edge, Safari,
 * Firefox) ships a speech engine already.
 *
 * This is Memora's concrete implementation of "auditory" content
 * mode (SensoryProfile.preferred_mode === "auditory"): rather than
 * requiring separately-authored audio narration per lesson (a real
 * content-authoring cost this project doesn't have covered yet), any
 * lesson's existing text can always be read aloud on demand.
 */
export function ListenButton({
  text,
  label = "Listen to this lesson",
  emphasized = false,
}: {
  text: string;
  label?: string;
  /** When true, renders as the primary-styled button instead of
   * outline — used when this is the student's preferred content mode
   * (SensoryProfile.preferred_mode === "auditory"), so it reads as
   * the emphasized action rather than an equal-weight option. */
  emphasized?: boolean;
}) {
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(true);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  function toggle() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    // Slightly slower than default (1.0) — easier to follow along
    // with the on-screen text at the same time, which matters more
    // here than for general-purpose TTS use.
    utterance.rate = 0.92;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    utteranceRef.current = utterance;

    window.speechSynthesis.cancel(); // clear any stray queued utterance first
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }

  if (!supported) return null;

  return (
    <Button variant={emphasized ? "primary" : "outline"} size="sm" onClick={toggle} className="gap-1.5">
      {speaking ? <Square className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
      {speaking ? "Stop" : label}
    </Button>
  );
}
