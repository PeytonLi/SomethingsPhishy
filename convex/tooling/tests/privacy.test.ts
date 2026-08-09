import { describe, expect, it } from "vitest";
import { scrubPii } from "../../privacy";

describe("scrubPii", () => {
  it("removes email addresses and phone numbers before persistence", () => {
    const scrubbed = scrubPii("Email jane@example.com or call +1 (415) 555-0123");
    expect(scrubbed).not.toContain("jane@example.com");
    expect(scrubbed).not.toContain("415");
  });

  it("removes street addresses and long digit runs", () => {
    const scrubbed = scrubPii("Ship to 123 Main Street, account 123456789");
    expect(scrubbed).not.toContain("123 Main Street");
    expect(scrubbed).not.toContain("123456789");
  });
});
