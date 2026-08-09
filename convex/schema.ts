import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  domainIntel: defineTable({
    domain: v.string(),
    registeredAt: v.optional(v.number()),
    ageDays: v.optional(v.number()),
    safeBrowsingVerdict: v.optional(v.string()),
    isOfficialSoftwareDomain: v.optional(v.boolean()),
    fetchedAt: v.number(),
    ttlSeconds: v.number(),
  }).index("by_domain", ["domain"]),

  communityFlags: defineTable({
    domain: v.string(),
    dangerCount: v.number(),
    distinctReporters: v.number(),
    reporterIds: v.array(v.string()),
    topFindingCodes: v.array(v.string()),
    firstSeen: v.number(),
    lastSeen: v.number(),
    promoted: v.boolean(),
  })
    .index("by_domain", ["domain"])
    .index("by_promoted", ["promoted", "lastSeen"]),

  scamCorpus: defineTable({
    sourceText: v.string(),
    scamType: v.string(),
    provenance: v.string(),
    embedding: v.array(v.float64()),
  }).vectorIndex("by_embedding", {
    vectorField: "embedding",
    dimensions: 1536,
    filterFields: ["scamType"],
  }),

  scans: defineTable({
    userId: v.string(),
    surface: v.string(),
    verdict: v.string(),
    domain: v.optional(v.string()),
    findingCodes: v.array(v.string()),
    findingsRedacted: v.array(
      v.object({
        code: v.string(),
        severity: v.number(),
        title: v.string(),
        evidence: v.string(),
      }),
    ),
    textHash: v.optional(v.string()),
    acknowledged: v.boolean(),
    createdAt: v.number(),
  })
    .index("by_user_time", ["userId", "createdAt"])
    .index("by_verdict_time", ["verdict", "createdAt"]),

  guardians: defineTable({
    protectedUserId: v.string(),
    guardianUserId: v.string(),
    guardianEmail: v.optional(v.string()),
    guardianPhone: v.optional(v.string()),
    alertOn: v.array(v.string()),
    consentGivenAt: v.number(),
  })
    .index("by_protected", ["protectedUserId"])
    .index("by_guardian", ["guardianUserId"]),
});
