import { describe, expect, it } from "vitest";
import { licenceUrl } from "./licence-url";

describe("licenceUrl", () => {
  it("links every CC id the release uses to its deed", () => {
    expect(licenceUrl("CC-BY-4.0")).toBe("https://creativecommons.org/licenses/by/4.0/");
    expect(licenceUrl("CC-BY-SA-4.0")).toBe("https://creativecommons.org/licenses/by-sa/4.0/");
    expect(licenceUrl("CC-BY-2.0")).toBe("https://creativecommons.org/licenses/by/2.0/");
    expect(licenceUrl("CC-BY-SA-3.0-DE")).toBe("https://creativecommons.org/licenses/by-sa/3.0/de/");
    expect(licenceUrl("CC0-1.0")).toBe("https://creativecommons.org/publicdomain/zero/1.0/");
  });
  it("gives no link without a deed", () => {
    expect(licenceUrl("public-domain")).toBeNull();
    expect(licenceUrl("press-kit")).toBeNull();
    expect(licenceUrl(undefined)).toBeNull();
  });
});
