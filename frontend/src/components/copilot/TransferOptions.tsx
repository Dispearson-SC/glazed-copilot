import { useApi } from "../../ApiContext";
import { isUnavailable } from "../../api";
import { SOON_TEXT, confLabelFor } from "../../data/copilot";
import { usd } from "../../format";
import type { Range3, TransferOptionsResponse } from "../../types";
import { usePolling } from "../../usePolling";
import { Bone, Loading } from "./Skeleton";

const REASONS_ES: Record<string, string> = {
  no_receiver_deficit: "Ninguna tienda necesita este producto",
  no_surplus: "No hay excedente para trasladar",
};

const signed = (n: number) => `${n < 0 ? "-" : "+"}${usd(Math.abs(n))}`;
const netText = (r: Range3): string => {
  const { low, mid, high } = r;
  if (low != null && high != null && low !== high) return `${signed(low)} a ${signed(high)}`;
  const one = mid ?? low ?? high;
  return one == null ? "Sin datos" : signed(one);
};

/** Stock-transfer options of the case (GET /transfers/options), shown inside the analysis of a "Oportunidad de traslado". */
export default function TransferOptions({ caseId, sku, issueId }: { caseId: string; sku?: string; issueId?: string }) {
  const api = useApi();
  const res = usePolling<TransferOptionsResponse>(() => api.getTransferOptions(caseId), 60_000, false, [caseId]);

  if (res.loading)
    return (
      <Loading label="Cargando traslados" className="flex flex-col gap-2">
        <Bone className="h-4 w-32" />
        <Bone className="h-24 w-full rounded-2xl" />
      </Loading>
    );
  if (res.error) {
    return (
      <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">
        {isUnavailable(res.error) ? SOON_TEXT : `No se pudieron cargar los traslados: ${res.error.message}`}
      </p>
    );
  }
  const data = res.data;
  if (!data) return null;
  // The endpoint lists every option of the case: a card shows only those of its own issue/product.
  const options = data.options.filter((o) => (o.issue_id && issueId ? o.issue_id === issueId : Boolean(sku) && o.sku === sku));
  if (options.length === 0) {
    const why =
      data.options.length > 0
        ? "No hay traslados recomendados para este producto"
        : data.reason_es || (data.reason ? REASONS_ES[data.reason] : undefined) || "No hay traslados recomendados por ahora";
    return <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">{why}</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      <span className="flex items-center gap-1.5 font-label-md text-label-md uppercase text-secondary">
        <span aria-hidden="true" className="material-symbols-outlined text-[16px]">swap_horiz</span>
        Opciones de traslado
      </span>
      {options.map((o) => (
        <div key={o.option_id} data-testid="transfer-option" className="flex flex-col gap-1 rounded-2xl bg-surface-container p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate font-body-md text-body-md font-semibold text-primary">{o.to_store_name}</span>
            <span className="flex-shrink-0 font-label-md text-label-md font-semibold normal-case tracking-normal text-secondary">{o.qty} unidades</span>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 font-label-sm text-label-sm font-normal text-on-surface-variant">
            <span>Costo {usd(o.transfer_cost_usd)}</span>
            <span>Neto {netText(o.net_usd)}</span>
            <span>{confLabelFor(o.confidence.calibrated)} {o.confidence.score == null ? "Sin datos" : `${Math.round(o.confidence.score * 100)}%`}</span>
            <span>Vence el {o.expires_on}</span>
          </div>
          <p className="m-0 text-[13px] leading-[19px] text-on-surface">{o.rationale_es}</p>
        </div>
      ))}
    </div>
  );
}
