import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

const PROMOTION_THRESHOLD = 3;

function normalizeDomain(domain: string): string {
  return domain.trim().toLowerCase().replace(/^\.+|\.+$/g, "");
}

export const getCommunityFlag = query({
  args: { domain: v.string() },
  handler: (ctx, { domain }) =>
    ctx.db
      .query("communityFlags")
      .withIndex("by_domain", (q) => q.eq("domain", normalizeDomain(domain)))
      .unique(),
});

export const reportDanger = mutation({
  args: {
    domain: v.string(),
    codes: v.array(v.string()),
    userId: v.string(),
  },
  handler: async (ctx, { domain, codes, userId }) => {
    const normalized = normalizeDomain(domain);
    const existing = await ctx.db
      .query("communityFlags")
      .withIndex("by_domain", (q) => q.eq("domain", normalized))
      .unique();
    const now = Date.now();

    if (!existing) {
      const reporterIds = [userId];
      const id = await ctx.db.insert("communityFlags", {
        domain: normalized,
        dangerCount: 1,
        distinctReporters: 1,
        reporterIds,
        topFindingCodes: [...new Set(codes)].slice(0, 5),
        firstSeen: now,
        lastSeen: now,
        promoted: false,
      });
      return { id, distinctReporters: 1, promoted: false };
    }

    if (existing.reporterIds.includes(userId)) {
      return {
        id: existing._id,
        distinctReporters: existing.distinctReporters,
        promoted: existing.promoted,
      };
    }

    const reporterIds = [...existing.reporterIds, userId];
    const distinctReporters = reporterIds.length;
    const promoted = distinctReporters >= PROMOTION_THRESHOLD;
    await ctx.db.patch(existing._id, {
      dangerCount: existing.dangerCount + 1,
      distinctReporters,
      reporterIds,
      topFindingCodes: [...new Set([...existing.topFindingCodes, ...codes])].slice(0, 5),
      lastSeen: now,
      promoted,
    });
    return { id: existing._id, distinctReporters, promoted };
  },
});
