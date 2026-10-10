import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import IssueDetail from "./IssueDetail";
import { fakeApi } from "./test/helpers";
import { issueA } from "./test/fixtures";

const open = (api = fakeApi(), issue = issueA) =>
  render(
    <ApiProvider api={api}>
      <IssueDetail issue={issue} caseId="c1" />
    </ApiProvider>,
  );

describe("IssueDetail", () => {
  it("lists evidence and data caveats", () => {
    open();
    expect(screen.getByText(/ventas_diarias/)).toBeInTheDocument();
    expect(screen.getByText(/últimos 14 días/)).toBeInTheDocument();
    expect(screen.getByText("sin datos de merma de la semana pasada")).toBeInTheDocument();
  });

  it("renders one card per option with net, range, tier badge and reasons", () => {
    open();
    const card = screen.getByTestId("option-o-n2");
    expect(within(card).getByText("$80.00")).toBeInTheDocument();
    expect(within(card).getByText("$20.00 – $160.00")).toBeInTheDocument();
    expect(within(card).getByText("N2 propuesta")).toBeInTheDocument();
    expect(within(card).getByText(/monto sobre umbral/)).toBeInTheDocument();
    expect(within(card).getByText(/proveedor cierra mañana/)).toBeInTheDocument();
    expect(within(card).getByText(/sobrante si baja la demanda/)).toBeInTheDocument();
    expect(within(card).getByText(/merma Δ \$10\.00/)).toBeInTheDocument();
    expect(within(card).getByText(/ventas perdidas Δ -\$100\.00/)).toBeInTheDocument();
  });

  it("shows 'baja confianza' under 0.5 and a confidence bar", () => {
    open();
    const low = screen.getByTestId("option-o-n2");
    expect(within(low).getByText("baja confianza")).toBeInTheDocument();
    expect(within(low).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(within(screen.getByTestId("option-o-n3")).queryByText("baja confianza")).toBeNull();
  });

  it("highlights the most viable option (highest net with tier != N0)", () => {
    open();
    expect(screen.getByTestId("option-o-n3")).toHaveClass("best");
    expect(screen.getByTestId("option-o-n0")).not.toHaveClass("best");
    expect(screen.getByTestId("option-o-n2")).not.toHaveClass("best");
  });

  it("always shows the cost of doing nothing on the do_nothing card", () => {
    open();
    const card = screen.getByTestId("option-o-nothing");
    expect(within(card).getByText(/costo de no actuar/i)).toBeInTheDocument();
    expect(within(card).getByText("$120.00")).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Proponer esta opción" })).toBeNull();
  });

  it("proposes by option id, then lets the user approve", async () => {
    const api = fakeApi();
    open(api);
    const card = screen.getByTestId("option-o-n3");
    await userEvent.click(within(card).getByRole("button", { name: "Proponer esta opción" }));
    expect(api.proposeOption).toHaveBeenCalledWith(
      expect.objectContaining({ case_id: "c1", issue_id: "i1", option_id: "o-n3" }),
    );
    await userEvent.click(await within(card).findByRole("button", { name: "Aprobar" }));
    expect(api.decide).toHaveBeenCalledWith("p9", { approved: true });
  });

  it("does not offer to propose N0 options", () => {
    open();
    expect(within(screen.getByTestId("option-o-n0")).queryByRole("button", { name: "Proponer esta opción" })).toBeNull();
  });

  it("shows an error when proposing fails", async () => {
    const api = fakeApi({ proposeOption: vi.fn(async () => { throw new Error("boom"); }) });
    open(api);
    await userEvent.click(within(screen.getByTestId("option-o-n3")).getByRole("button", { name: "Proponer esta opción" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});
