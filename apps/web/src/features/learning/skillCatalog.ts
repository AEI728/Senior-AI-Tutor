import type { CSSProperties } from "react";
export const skillMeta: Record<
  string,
  { name: string; color: string; tint: string; course: string }
> = {
  "home-gardening": {
    name: "家庭园艺",
    color: "#52724f",
    tint: "#e5eee2",
    course: "repotting-basics",
  },
  calligraphy: {
    name: "书法",
    color: "#9d2f26",
    tint: "#f4e5df",
    course: "calligraphy-lines",
  },
  photography: {
    name: "摄影",
    color: "#28615c",
    tint: "#e1eeeb",
    course: "phone-composition",
  },
  music: {
    name: "乐器",
    color: "#b05c27",
    tint: "#f6e8da",
    course: "rhythm-basics",
  },
};
export const skillStyle = (id: string) =>
  ({
    "--skill-color": skillMeta[id]?.color || "#2f4942",
    "--skill-tint": skillMeta[id]?.tint || "#e5eee2",
  }) as CSSProperties;
export const cleanTitle = (s: string) =>
  s.replace(/（内部测试）|\(内部测试\)/g, "");
