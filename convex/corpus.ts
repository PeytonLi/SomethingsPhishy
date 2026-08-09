import { v } from "convex/values";
import { internal } from "./_generated/api";
import { action, internalAction, internalMutation } from "./_generated/server";
import { scrubPii } from "./privacy";

const DIMENSIONS = 1536;

export const similarScams = action({
  args: {
    embedding: v.array(v.float64()),
    scamType: v.optional(v.string()),
  },
  handler: async (ctx, { embedding, scamType }) => {
    if (embedding.length !== DIMENSIONS) {
      throw new Error(`Embedding must contain ${DIMENSIONS} values`);
    }
    const results = await ctx.vectorSearch("scamCorpus", "by_embedding", {
      vector: embedding,
      limit: 5,
      filter: scamType ? (q) => q.eq("scamType", scamType) : undefined,
    });
    return results.map((result) => ({
      ...result,
      maxSeverity: "MEDIUM" as const,
      decisive: false as const,
    }));
  },
});

export const insertCorpusItem = internalMutation({
  args: {
    sourceText: v.string(),
    scamType: v.string(),
    provenance: v.string(),
    embedding: v.array(v.float64()),
  },
  handler: async (ctx, args) => ctx.db.insert("scamCorpus", args),
});

export const ingestCorpusItem = action({
  args: {
    text: v.string(),
    type: v.string(),
    embedding: v.array(v.float64()),
    consentGiven: v.boolean(),
    provenance: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    if (!args.consentGiven) throw new Error("Corpus contribution requires explicit consent");
    if (args.embedding.length !== DIMENSIONS) {
      throw new Error(`Embedding must contain ${DIMENSIONS} values`);
    }
    return ctx.runMutation(internal.corpus.insertCorpusItem, {
      sourceText: scrubPii(args.text),
      scamType: args.type,
      provenance: args.provenance ?? "curated",
      embedding: args.embedding,
    });
  },
});

export const refreshThreatFeeds = internalAction({
  args: {},
  handler: async () => {
    // Feed credentials and embedding provider are optional. Keeping this job a
    // no-op is safer than persisting unembedded or unsanitized source text.
    return { refreshed: 0, reason: "feed provider not configured" };
  },
});
