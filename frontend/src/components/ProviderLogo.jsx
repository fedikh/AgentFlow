import React from "react";
import openaiLogo from "../assets/providers/openai.png";
import anthropicLogo from "../assets/providers/anthropic.png";
import geminiLogo from "../assets/providers/gemini.png";
import groqLogo from "../assets/providers/groq.png";
import ollamaLogo from "../assets/providers/ollama.png";
import voyageLogo from "../assets/providers/voyage.png";

/**
 * ProviderLogo — real official brand logos as PNG images.
 *
 * Put the PNG files in:  src/assets/providers/
 *   openai.png  anthropic.png  gemini.png  groq.png  ollama.png  voyage.png
 *
 * Usage:  <ProviderLogo family="OPENAI" size={20} />
 */
const LOGOS = {
  OPENAI: openaiLogo,
  ANTHROPIC: anthropicLogo,
  GOOGLE: geminiLogo, // Gemini = Google's model logo
  GEMINI: geminiLogo,
  GROQ: groqLogo,
  OLLAMA: ollamaLogo,
  VOYAGE: voyageLogo,
};

const ProviderLogo = ({ family, size = 20 }) => {
  const src = LOGOS[(family || "").toUpperCase()];
  if (!src) {
    return (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          background: "#e2e8f0",
          display: "inline-block",
          flexShrink: 0,
        }}
      />
    );
  }
  return (
    <img
      src={src}
      alt={family}
      width={size}
      height={size}
      style={{ flexShrink: 0, display: "block", objectFit: "contain" }}
    />
  );
};

export default ProviderLogo;
