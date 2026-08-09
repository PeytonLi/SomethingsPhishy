import { v } from "convex/values";
import { action, internalAction, internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";

export const getAlertContext = internalQuery({
  args: { scanId: v.id("scans") },
  handler: async (ctx, { scanId }) => {
    const scan = await ctx.db.get(scanId);
    if (!scan || scan.acknowledged || scan.verdict !== "DANGER") return null;
    const guardians = await ctx.db
      .query("guardians")
      .withIndex("by_protected", (q) => q.eq("protectedUserId", scan.userId))
      .collect();
    return {
      scan,
      guardians: guardians.filter(
        (guardian) => guardian.consentGivenAt > 0 && guardian.alertOn.includes("DANGER"),
      ),
    };
  },
});

export const notifyGuardian = action({
  args: { scanId: v.id("scans") },
  handler: async (ctx, { scanId }) => {
    // Reading this query after 60 seconds makes acknowledgement cancel escalation.
    // Delivery providers are intentionally optional; the reactive feed is primary.
    return ctx.runQuery(internal.alerts.getAlertContext, { scanId });
  },
});

export const notifyGuardianScheduled = internalAction({
  args: { scanId: v.id("scans") },
  handler: async (ctx, { scanId }) =>
    ctx.runQuery(internal.alerts.getAlertContext, { scanId }),
});
