import { describe, expect, it } from "vitest";

import { focusRing } from "../src/lib/tokens";

function luminance(hex: string): number {
  const channels = hex.slice(1).match(/.{2}/g)!.map((channel) => {
    const value = Number.parseInt(channel, 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(first: string, second: string): number {
  const [bright, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (bright + 0.05) / (dark + 0.05);
}

describe("focusRing", () => {
  it.each(["#FFFFFF", "#F3F6FA"])(
    "has at least 3:1 non-text contrast against %s",
    (background) => {
      expect(contrast(focusRing, background)).toBeGreaterThanOrEqual(3);
    },
  );
});
