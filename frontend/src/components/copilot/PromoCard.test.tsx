import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildPendingItems } from "../../data/copilot";
import { analysisPromoAlt, pendingPromo } from "../../test/copilotFixtures";
import AnalysisCard from "./AnalysisCard";

describe("AnalysisCard with an activate_promo alternative", () => {
  it("lists 'Activar promoción' with its numbers under Alternativas", () => {
    const [item] = buildPendingItems(pendingPromo, "2026-07-19");
    render(<AnalysisCard item={item} analysis={{ status: "ok", data: analysisPromoAlt }} mode="dialogo" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText(/Activar promoción −20% por 5 días \(lun 20 jul–vie 24 jul\) \(efecto neto \$31\.20\)/)).toBeInTheDocument();
    expect(screen.getByText(/Vende ~36 de 48 unidades en riesgo/)).toBeInTheDocument();
    expect(screen.getByText(/confianza media/)).toBeInTheDocument();
    expect(screen.getByText(/No hacer nada/)).toBeInTheDocument();
  });
});
