import type { currencyEnum } from "./schema.js";

export type Currency = (typeof currencyEnum.enumValues)[number];

// Static rate table (1 unit of currency -> USD). Not live-fetched: keeps the
// MCP tools and their tests deterministic. Update FX_AS_OF when refreshing.
export const FX_AS_OF = "2026-07-04";

export const FX_RATES: Record<Currency, number> = {
  USD: 1,
  EUR: 1.144,
  CAD: 0.7043,
  MXN: 0.057,
  TRY: 0.0214,
};

export function toUsd(amount: number, currency: Currency): number {
  return amount * FX_RATES[currency];
}
