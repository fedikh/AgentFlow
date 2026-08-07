import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/*
 * AnswerBody — renders an agent answer as real Markdown.
 *
 * LLMs reply in Markdown (headings, bullet AND numbered lists, tables, code,
 * links, quotes). react-markdown + remark-gfm parse it properly instead of the
 * regex approximation we had, so tables and ordered lists finally render.
 *
 * Safety: react-markdown does NOT execute raw HTML by default — model output is
 * treated as text, never injected as markup.
 *
 * Styling lives in agentChat.css under .ac-md (one place, both chat pages).
 */
const AnswerBody = ({ text = "" }) => (
  <div className="ac-md">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // tables can be wider than the bubble — let them scroll on their own
        table: (props) => (
          <div className="ac-md-tablewrap">
            <table {...props} />
          </div>
        ),
        a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
      }}
    >
      {text}
    </ReactMarkdown>
  </div>
);

export default AnswerBody;
