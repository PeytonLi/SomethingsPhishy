import { cronJobs } from "convex/server";
import { internal } from "./_generated/api";

const crons = cronJobs();

crons.daily("refresh threat feeds", { hourUTC: 3, minuteUTC: 0 }, internal.corpus.refreshThreatFeeds);
crons.hourly("expire stale domain intel", { minuteUTC: 15 }, internal.intel.expireStaleIntel);

export default crons;
