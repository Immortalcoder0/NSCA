import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, ApiError } from "./client";

describe("ApiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("attaches X-Dev-Role header from localStorage or default", async () => {
    localStorage.setItem("nsca_dev_role", "lead_assessor");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    global.fetch = fetchMock;

    await apiClient.get("/campaigns");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-Dev-Role")).toBe("lead_assessor");
  });

  it("throws ApiError on HTTP error with parsed detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "Lead Assessor role required to issue campaign" }),
    });
    global.fetch = fetchMock;

    await expect(apiClient.post("/campaigns/CMP-001/issue")).rejects.toThrow(ApiError);
  });
});
