import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const REMOVED = [
  "pages/AlertsPage", "pages/CasesPage", "pages/PurchasesPage", "pages/TracePage", "pages/DecisionsPage",
  "pages/InventoryPage", "pages/WeekPage", "SimControl", "CentinelaPanel", "IssueDetail", "ComingSoon",
  "dashboard/BriefingCard", "dashboard/ContextChips", "dashboard/UpcomingCard", "dashboard/ForecastAccuracy", "issues",
];

describe("legacy code is gone", () => {
  it.each(REMOVED)("%s no longer exists", (name) => {
    expect(existsSync(`src/${name}.tsx`) || existsSync(`src/${name}.ts`)).toBe(false);
  });

  it("ships no legacy css layer, semaphore or reasoning links", () => {
    const css = readFileSync("src/index.css", "utf8");
    for (const legacy of [".card", ".panel", ".badge", ".lanes", ".light", ".timeline", "main button"]) expect(css).not.toContain(legacy);
    expect(readFileSync("src/pages/HomePage.tsx", "utf8")).not.toMatch(/semaphore|Alertas abiertas|Lo que se pierde/);
    expect(readFileSync("src/chat/ChatView.tsx", "utf8")).not.toContain("Ver razonamiento");
  });
});
