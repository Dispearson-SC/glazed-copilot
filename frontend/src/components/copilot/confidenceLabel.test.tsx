import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildPendingItems } from "../../data/copilot";
import { pendingA } from "../../test/copilotFixtures";
import ApprovalCard from "./ApprovalCard";

describe("ApprovalCard confidence label", () => {
  it("never claims 'calibrada' for an uncalibrated score", () => {
    const [item] = buildPendingItems({ ...pendingA, approvals: [{ ...pendingA.approvals[0], confidence: { score: 0.3, calibrated: false } }] }, "2026-07-19");
    render(<ApprovalCard item={item} onAnalyze={vi.fn()} />);
    expect(screen.getByText("Confianza estimada (sin calibrar)")).toBeInTheDocument();
    expect(screen.queryByText("Confianza calibrada")).toBeNull();
  });
});
