import React from "react";
import { BAAI, Jina } from "@lobehub/icons";
import { SiPostgresql, SiMysql } from "react-icons/si";
import { DiMsqlServer } from "react-icons/di";
import openaiLogo from "../assets/providers/openai.png";
import anthropicLogo from "../assets/providers/anthropic.png";
import geminiLogo from "../assets/providers/gemini.png";
import groqLogo from "../assets/providers/groq.png";
import ollamaLogo from "../assets/providers/ollama.png";
import voyageLogo from "../assets/providers/voyage.png";

/**
 * ProviderLogo — real official brand logos.
 *
 * PNG files in src/assets/providers/:
 *   openai.png  anthropic.png  gemini.png  groq.png  ollama.png  voyage.png
 * Families without a PNG (BAAI/BGE, Jina …) use SVG marks from @lobehub/icons.
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

/* SVG icon components for brands we have no PNG for (local embedding models). */
const ICON_COMPONENTS = {
  BAAI: BAAI, // BGE-M3 & other BGE models
  JINA: Jina, // jina-embeddings-*
};

/* Database dialect logos (Data Agent connection) — react-icons brand glyphs
   tinted in each engine's official color. Keys match DIALECTS names. */
const DB_ICONS = {
  POSTGRES: { Icon: SiPostgresql, color: "#336791" },
  MYSQL: { Icon: SiMysql, color: "#00758F" },
  MSSQL: { Icon: DiMsqlServer, color: "#CC2927" },
};

const ProviderLogo = ({ family, size = 20 }) => {
  const fam = (family || "").toUpperCase();
  const db = DB_ICONS[fam];
  if (db) return <db.Icon size={size} color={db.color} style={{ flexShrink: 0 }} />;
  const src = LOGOS[fam];
  if (!src) {
    const Icon = ICON_COMPONENTS[fam];
    if (Icon) return <Icon size={size} style={{ flexShrink: 0 }} />;
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
