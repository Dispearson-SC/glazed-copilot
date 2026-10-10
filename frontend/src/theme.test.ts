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
    expect(fonts["headline-sm"][0]).toBe("Poppins");
    expect(fonts["body-md"][0]).toBe("Plus Jakarta Sans");
  });

  it("loads the fonts and Material Symbols in index.html", () => {
    const html = readFileSync("index.html", "utf8");
    expect(html).toContain("Material+Symbols+Outlined");
    expect(html).toContain("Plus+Jakarta+Sans");
    expect(html).toContain("Poppins");
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
  it("loads the same fonts as the design source (plus the body font its tailwind config names)", () => {
    const html = readFileSync("index.html", "utf8");
    expect(html).toContain("family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900");
    expect(html).toContain("family=Poppins:ital,wght@0,200;0,300;0,400;0,500;0,600;0,700;0,800;1,200;1,300;1,400;1,500;1,600");
    expect(html).toContain("family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200");
    expect(html).toContain("Plus+Jakarta+Sans");
    expect(html).toContain('name="apple-mobile-web-app-capable"');
  });
});
