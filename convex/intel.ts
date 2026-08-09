import { v } from "convex/values";
import { api, internal } from "./_generated/api";
import { action, internalMutation, mutation, query } from "./_generated/server";

const DAY_MS = 86_400_000;
const DEFAULT_TTL_SECONDS = 86_400;

function normalizeDomain(domain: string): string {
  return domain.trim().toLowerCase().replace(/^\.+|\.+$/g, "");
}

export const getDomainIntel = query({
  args: { domain: v.string() },
  handler: async (ctx, { domain }) => {
    const intel = await ctx.db
      .query("domainIntel")
      .withIndex("by_domain", (q) => q.eq("domain", normalizeDomain(domain)))
      .unique();
    if (!intel) return null;
    return {
      ...intel,
      stale: Date.now() > intel.fetchedAt + intel.ttlSeconds * 1000,
    };
  },
});

const intelFields = {
  domain: v.string(),
  registeredAt: v.optional(v.number()),
  ageDays: v.optional(v.number()),
  safeBrowsingVerdict: v.optional(v.string()),
  isOfficialSoftwareDomain: v.optional(v.boolean()),
  fetchedAt: v.number(),
  ttlSeconds: v.number(),
};

async function writeIntel(ctx: any, args: any) {
  const domain = normalizeDomain(args.domain);
  const current = await ctx.db
    .query("domainIntel")
    .withIndex("by_domain", (q: any) => q.eq("domain", domain))
    .unique();
  const value = { ...args, domain };
  if (current) {
    await ctx.db.patch(current._id, value);
    return current._id;
  }
  return ctx.db.insert("domainIntel", value);
}

export const upsertDomainIntel = mutation({
  args: intelFields,
  handler: writeIntel,
});

export const upsertDomainIntelInternal = internalMutation({
  args: intelFields,
  handler: writeIntel,
});

export const refreshDomainIntel = action({
  args: { domain: v.string(), force: v.optional(v.boolean()) },
  handler: async (ctx, { domain, force }): Promise<any> => {
    const normalized = normalizeDomain(domain);
    const cached: any = await ctx.runQuery(api.intel.getDomainIntel, { domain: normalized });
    if (cached && !cached.stale && !force) return cached;

    const response = await fetch(`https://rdap.org/domain/${encodeURIComponent(normalized)}`, {
      headers: { Accept: "application/rdap+json" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) throw new Error(`RDAP lookup failed (${response.status})`);
    const body = (await response.json()) as {
      events?: Array<{ eventAction?: string; eventDate?: string }>;
    };
    const registration = body.events?.find((event) => event.eventAction === "registration");
    const parsed = registration?.eventDate ? Date.parse(registration.eventDate) : NaN;
    const registeredAt = Number.isFinite(parsed) ? parsed : undefined;
    const fetchedAt = Date.now();
    const ageDays = registeredAt === undefined
      ? undefined
      : Math.max(0, Math.floor((fetchedAt - registeredAt) / DAY_MS));

    await ctx.runMutation(internal.intel.upsertDomainIntelInternal, {
      domain: normalized,
      registeredAt,
      ageDays,
      fetchedAt,
      ttlSeconds: DEFAULT_TTL_SECONDS,
    });
    return ctx.runQuery(api.intel.getDomainIntel, { domain: normalized });
  },
});

export const expireStaleIntel = internalMutation({
  args: {},
  handler: async (ctx) => {
    const now = Date.now();
    const rows = await ctx.db.query("domainIntel").collect();
    const stale = rows.filter((row) => now > row.fetchedAt + row.ttlSeconds * 1000);
    await Promise.all(stale.map((row) => ctx.db.delete(row._id)));
    return stale.length;
  },
});
