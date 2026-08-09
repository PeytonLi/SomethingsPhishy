import { anyApi } from "convex/server";

// This keeps the dashboard independently buildable while Track D owns generated API files.
// The function names are the frozen contract from PRD §6.7.
export const api = anyApi;
