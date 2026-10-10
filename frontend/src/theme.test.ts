import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import tailwind from "../tailwind.config";
import viteConfig from "../vite.config";

describe("Artisanal Roast theme", () => {
  it("defines the design tokens", () => {
    const colors = tailwind.theme?.extend?.colors as Record<string, string>;
    expect(colors.primary).toBe("#331b11");
    expect(colors["primary-container"]).toBe("#4b3025");
    expect(colors.surface).toBe("#fff8f4");
    expect(colors["on-tertiary-container"]).toBe("#cb9564");
    const fonts = tailwind.theme?.extend?.fontFamily as Record<string, string[]>;
    for (const k of ["display-hero", "display-hero-mobile", "headline-lg", "headline-md", "headline-sm"]) expect(fonts[k][0]).toBe("Playfair Display");
    for (const k of ["metric-value", "metric-value-sm", "body-lg", "body-md", "label-md", "label-sm"]) expect(fonts[k][0]).toBe("Plus Jakarta Sans");
    expect(fonts["body-md"][0]).toBe("Plus Jakarta Sans");
  });

  it("loads the fonts and Material Symbols in index.html", () => {
    const html = readFileSync("index.html", "utf8");
    expect(html).toContain("Material+Symbols+Outlined");
    expect(html).toContain("Plus+Jakarta+Sans");
    expect(html).toContain("Playfair+Display");
    expect(html).toContain('content="#4b3025"');
  });

  it("proxies /api to the host backend port 8100 by default", () => {
    const proxy = (viteConfig as { server?: { proxy?: Record<string, { target: string }> } }).server?.proxy;
    expect(proxy?.["/api"].target).toBe(process.env.VITE_API_URL ?? "http://localhost:8100");
  });

  it("ships brand assets", () => {
    for (const f of ["Logo.png", "Logo-Full.png", "favicon.svg", "favicon-32.png", "apple-touch-icon.png", "pwa-192x192.png", "pwa-512x512.png", "maskable-512x512.png"])
      expect(() => readFileSync(`public/${f}`)).not.toThrow();
  });
});

describe("legacy css layer", () => {
  it("is gone: only the design base and utilities remain", () => {
    const css = readFileSync("src/index.css", "utf8");
    expect(css).not.toContain("#c2185b");
    expect(css).not.toMatch(/\.card|\.badge|main button/);
    expect(css).toContain(".pb-safe");
    expect(css).toContain(".pt-safe");
  });
});

describe("design parity", () => {
  it("loads Playfair Display (DESIGN.md display/headline), Plus Jakarta Sans and Material Symbols", () => {
    const html = readFileSync("index.html", "utf8");
    expect(html).toContain("family=Playfair+Display:wght@500;600;700");
    expect(html).toContain("family=Plus+Jakarta+Sans:wght@400;500;600;700");
    expect(html).toContain("family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200");
    expect(html).not.toContain("Poppins");
    expect(html).toContain('name="apple-mobile-web-app-capable"');
  });

  it("types display and headline roles as in DESIGN.md", () => {
    const sizes = tailwind.theme?.extend?.fontSize as Record<string, [string, { lineHeight: string; fontWeight: string }]>;
    expect(sizes["display-hero"][0]).toBe("40px");
    expect(sizes["display-hero-mobile"][1].fontWeight).toBe("600");
    expect(sizes["headline-lg"][0]).toBe("28px");
    expect(sizes["headline-md"][1].fontWeight).toBe("500");
    expect(sizes["headline-sm"][0]).toBe("18px");
  });
});
