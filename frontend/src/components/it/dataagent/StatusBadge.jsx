import React from "react";
import { STATUS } from "./ui";

export default function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.draft;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20,
      background: s.bg, color: s.color, flexShrink: 0,
    }}>
      {s.label}
    </span>
  );
}
