import { describe, expect, it } from "vitest";
import { generationTitle } from "./generation-title";

const t = (make_name: string, model_name: string, generation_name: string) => generationTitle({ make_name, model_name, generation_name });

describe("generationTitle", () => {
  it("never repeats the model name (T-135 S1, T-169)", () => {
    expect(t("Kia", "Niro EV", "e-Niro (Gen 1, DE)")).toBe("Kia e-Niro (Gen 1, DE)");
    expect(t("Kia", "Niro EV", "Niro EV (Gen 2, SG2)")).toBe("Kia Niro EV (Gen 2, SG2)");
    expect(t("Skoda", "Enyaq", "Enyaq")).toBe("Skoda Enyaq");
    expect(t("Audi", "e-tron", "e-tron (GE)")).toBe("Audi e-tron (GE)");
    expect(t("Honda", "e", "Honda e")).toBe("Honda e");
  });

  it("keeps the model name when the generation name doesn't start with it", () => {
    expect(t("Kia", "Soul EV", "Gen 2 (e-Soul, SK3)")).toBe("Kia Soul EV Gen 2 (e-Soul, SK3)");
    expect(t("Volkswagen", "e-Golf", "Mk7")).toBe("Volkswagen e-Golf Mk7");
  });
});
