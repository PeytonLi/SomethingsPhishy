/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as alerts from "../alerts.js";
import type * as community from "../community.js";
import type * as corpus from "../corpus.js";
import type * as crons from "../crons.js";
import type * as guardians from "../guardians.js";
import type * as http from "../http.js";
import type * as intel from "../intel.js";
import type * as privacy from "../privacy.js";
import type * as scans from "../scans.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  alerts: typeof alerts;
  community: typeof community;
  corpus: typeof corpus;
  crons: typeof crons;
  guardians: typeof guardians;
  http: typeof http;
  intel: typeof intel;
  privacy: typeof privacy;
  scans: typeof scans;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
