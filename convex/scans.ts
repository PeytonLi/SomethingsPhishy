import { v } from "convex/values";
import { internal } from "./_generated/api";
import { mutation, query } from "./_generated/server";
import { scrubPii } from "./privacy";

const finding = v.object({
  code: v.string(),
  severity: v.number(),
  title: v.string(),
  evidence: v.string(),
});

export const recordScan = mutation({
  args: {
    userId: v.string(),
    surface: v.string(),
    verdict: v.string(),
    domain: v.optional(v.string()),
    findingCodes: v.array(v.string()),
    findingsRedacted: v.array(finding),
    textHash: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const scanId = await ctx.db.insert("scans", {
      ...args,
      domain: args.domain?.trim().toLowerCase(),
      findingsRedacted: args.findingsRedacted.map((item) => ({
        ...item,
        title: scrubPii(item.title),
        evidence: scrubPii(item.evidence),
      })),
      acknowledged: false,
      createdAt: now,
    });

    if (args.verdict === "DANGER") {
      await ctx.scheduler.runAfter(60_000, internal.alerts.notifyGuardian, {
        scanId,
      });
    }
    return scanId;
  },
});

export const recentScans = query({
  args: { userId: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, { userId, limit }) =>
    ctx.db
      .query("scans")
      .withIndex("by_user_time", (q) => q.eq("userId", userId))
      .order("desc")
      .take(Math.min(Math.max(limit ?? 50, 1), 100)),
});

export const guardianFeed = query({
  args: { guardianUserId: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, { guardianUserId, limit }) => {
    const links = await ctx.db
      .query("guardians")
      .withIndex("by_guardian", (q) => q.eq("guardianUserId", guardianUserId))
      .collect();
    const allowedUsers = new Set(
      links.filter((link) => link.consentGivenAt > 0).map((link) => link.protectedUserId),
    );
    if (allowedUsers.size === 0) return [];

    const scans = await Promise.all(
      [...allowedUsers].map((userId) =>
        ctx.db
          .query("scans")
          .withIndex("by_user_time", (q) => q.eq("userId", userId))
          .order("desc")
          .take(Math.min(Math.max(limit ?? 50, 1), 100)),
      ),
    );
    return scans
      .flat()
      .sort((a, b) => b.createdAt - a.createdAt)
      .slice(0, Math.min(Math.max(limit ?? 50, 1), 100));
  },
});

export const acknowledge = mutation({
  args: { scanId: v.id("scans") },
  handler: async (ctx, { scanId }) => {
    await ctx.db.patch(scanId, { acknowledged: true });
  },
});
