import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

describe("AnalysisCard choosing an alternative", () => {
  const [item] = buildPendingItems(pendingPromo, "2026-07-19");
  const view = (over: Partial<Parameters<typeof AnalysisCard>[0]> = {}, data = analysisPromoAlt) =>
    render(<AnalysisCard item={item} analysis={{ status: "ok", data }} mode="dialogo" open onApprove={() => {}} onReject={() => {}} onChoose={() => {}} {...over} />);

  it("chooses the alternative's own option_id, never the recommendation's", () => {
    const onChoose = vi.fn();
    view({ onChoose });
    const btn = screen.getByRole("button", { name: "Elegir No hacer nada" });
    expect(btn).toHaveTextContent("Elegir esta");
    fireEvent.click(btn);
    expect(onChoose).toHaveBeenCalledWith(item, { optionId: "a0f43dce40dc", label: "No hacer nada" });
    expect(JSON.stringify(onChoose.mock.calls)).not.toContain(analysisPromoAlt.recommendation.option_id);
  });

  it("disables every approve/choose button while a decision is in flight", () => {
    view({ busy: true });
    for (const name of [/Elegir/, /Aprobar|Aceptar/, /Rechazar/]) for (const b of screen.getAllByRole("button", { name })) expect(b).toBeDisabled();
  });

  it("shows no button for an alternative without option_id", () => {
    const data = { ...analysisPromoAlt, dialog: { ...analysisPromoAlt.dialog, alternatives: [{ option_id: "", label: "Solo texto", net_usd_mid: null }] } };
    view({}, data);
    expect(screen.getByText(/Solo texto/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Elegir/ })).toBeNull();
  });

  it("renders the promo lines of an activate_promo alternative and lets it be chosen", () => {
    const onChoose = vi.fn();
    view({ onChoose });
    expect(screen.getByText(/Vende ~36 de 48 unidades en riesgo/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `Elegir ${analysisPromoAlt.dialog.alternatives[0].label}` }));
    expect(onChoose.mock.calls[0][1].optionId).toBe(analysisPromoAlt.dialog.alternatives[0].option_id);
  });
});
