import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const REMOVED = [
  "pages/AlertsPage", "pages/CasesPage", "pages/PurchasesPage", "pages/TracePage", "pages/DecisionsPage",
  "pages/InventoryPage", "pages/WeekPage", "SimControl", "CentinelaPanel", "IssueDetail", "ComingSoon",
  "pages/HomePage", "shell/TopBar", "shell/BottomNav", "dashboard/Hero", "dashboard/TrendChart", "dashboard/ForecastChart", "dashboard/BriefingCard", "dashboard/ContextChips", "dashboard/UpcomingCard", "dashboard/ForecastAccuracy", "issues",
  "pages/DashboardPage", "pages/LoginPage", "pages/ChatPage", "chat/FloatingChat", "chat/ChatView", "components/PageShell", "components/TopBar", "components/BottomNav",
];

describe("legacy code is gone", () => {
  it.each(REMOVED)("%s no longer exists", (name) => {
    expect(existsSync(`src/${name}.tsx`) || existsSync(`src/${name}.ts`)).toBe(false);
  });

  it("ships no legacy css layer, semaphore or reasoning links", () => {
    const css = readFileSync("src/index.css", "utf8");
    for (const legacy of [".card", ".panel", ".badge", ".lanes", ".light", ".timeline", "main button"]) expect(css).not.toContain(legacy);
  });
});
