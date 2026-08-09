import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

// The guardians table was defined and read by scans.guardianFeed, but nothing
// could write it — so the feed always returned []. Consent is explicit here:
// linking requires the caller to pass consent, and revoking clears the link
// rather than hiding it, because a safety net you cannot leave is surveillance.

export const link = mutation({
  args: {
    protectedUserId: v.string(),
    guardianUserId: v.string(),
    guardianEmail: v.optional(v.string()),
    guardianPhone: v.optional(v.string()),
    alertOn: v.optional(v.array(v.string())),
    consentGiven: v.boolean(),
  },
  handler: async (ctx, args) => {
    if (!args.consentGiven) {
      throw new Error("Guardian links require explicit consent from both sides.");
    }
    const existing = await ctx.db
      .query("guardians")
      .withIndex("by_protected", (q) => q.eq("protectedUserId", args.protectedUserId))
      .collect();
    const match = existing.find((row) => row.guardianUserId === args.guardianUserId);

    const value = {
      protectedUserId: args.protectedUserId,
      guardianUserId: args.guardianUserId,
      guardianEmail: args.guardianEmail,
      guardianPhone: args.guardianPhone,
      alertOn: args.alertOn ?? ["DANGER"],
      consentGivenAt: Date.now(),
    };
    if (match) {
      await ctx.db.patch(match._id, value);
      return match._id;
    }
    return ctx.db.insert("guardians", value);
  },
});

export const unlink = mutation({
  args: { protectedUserId: v.string(), guardianUserId: v.string() },
  handler: async (ctx, { protectedUserId, guardianUserId }) => {
    const rows = await ctx.db
      .query("guardians")
      .withIndex("by_protected", (q) => q.eq("protectedUserId", protectedUserId))
      .collect();
    for (const row of rows.filter((r) => r.guardianUserId === guardianUserId)) {
      await ctx.db.delete(row._id);
    }
  },
});

// The protected user must always be able to see who is watching them.
export const myGuardians = query({
  args: { protectedUserId: v.string() },
  handler: async (ctx, { protectedUserId }) =>
    ctx.db
      .query("guardians")
      .withIndex("by_protected", (q) => q.eq("protectedUserId", protectedUserId))
      .collect(),
});
