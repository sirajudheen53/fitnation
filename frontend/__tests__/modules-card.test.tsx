import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { toast } from "sonner";
import { ModulesCard } from "@/features/settings/components/ModulesCard";
import {
  fetchTenantFeatureSettings,
  updateTenantFeatureFlags,
  errorMessage,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  fetchTenantFeatureSettings: jest.fn(),
  updateTenantFeatureFlags: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedFetch = fetchTenantFeatureSettings as jest.Mock;
const mockedUpdate = updateTenantFeatureFlags as jest.Mock;
const mockedErrorMessage = errorMessage as jest.Mock;

const settingsPayload = () => ({
  flags: { marketplace: true, ai_coach: true, ai_nutrition: true, body_analysis: true, reviews: false },
  catalog: [
    { key: "marketplace", label: "Marketplace", description: "Product catalogue, cart, and member orders.", default: true },
    { key: "ai_coach", label: "AI Coach", description: "Conversational AI workout coach and recommendations.", default: true },
    { key: "ai_nutrition", label: "AI Nutrition", description: "AI meal plans, macro tracking, shopping lists.", default: true },
    { key: "body_analysis", label: "Body Analysis", description: "AI body composition analysis and progress photos.", default: true },
    { key: "reviews", label: "Reviews", description: "Member reviews and replies.", default: true },
  ],
});

beforeEach(() => {
  jest.clearAllMocks();
  mockedFetch.mockResolvedValue(settingsPayload());
  mockedErrorMessage.mockImplementation((err: unknown) =>
    err instanceof Error ? err.message : "error",
  );
});

describe("ModulesCard (issue #63)", () => {
  it("renders every catalog module with its resolved on/off state", async () => {
    render(<ModulesCard />);

    expect(await screen.findByText("Marketplace")).toBeInTheDocument();

    expect(screen.getByRole("switch", { name: "Marketplace" })).toBeChecked(); // on
    expect(screen.getByRole("switch", { name: "AI Coach" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Reviews" })).not.toBeChecked(); // off

    expect(screen.getByTestId("modules-card")).toHaveTextContent("AI Nutrition");
    expect(screen.getByTestId("modules-card")).toHaveTextContent("Body Analysis");
  });

  it("PATCHes the toggled flag and persists the new state on success", async () => {
    mockedUpdate.mockResolvedValue({
      ...settingsPayload(),
      flags: { ...settingsPayload().flags, reviews: true },
    });
    render(<ModulesCard />);

    const reviewsToggle = await screen.findByRole("switch", { name: "Reviews" });
    expect(reviewsToggle).not.toBeChecked();

    fireEvent.click(reviewsToggle);

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith({ reviews: true }, "test-token"),
    );
    // Server-confirmed state sticks.
    await waitFor(() => expect(screen.getByRole("switch", { name: "Reviews" })).toBeChecked());
    expect(toast.success).toHaveBeenCalledWith("Reviews enabled");
    expect(screen.queryByTestId("modules-error")).not.toBeInTheDocument();
  });

  it("rolls back and shows an error banner when the save fails", async () => {
    mockedUpdate.mockRejectedValue(new Error("Only the gym owner can change modules"));
    render(<ModulesCard />);

    const reviewsToggle = await screen.findByRole("switch", { name: "Reviews" });
    fireEvent.click(reviewsToggle);

    // Optimistic flip, then rollback to off + readable banner.
    await waitFor(() => expect(screen.getByTestId("modules-error")).toHaveTextContent(/only the gym owner/i));
    expect(screen.getByRole("switch", { name: "Reviews" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "Marketplace" })).toBeChecked(); // others untouched
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("disables every toggle while a save is in flight", async () => {
    let resolveSave: (value: unknown) => void = () => {};
    mockedUpdate.mockImplementation(
      () => new Promise((resolve) => (resolveSave = resolve)),
    );
    render(<ModulesCard />);

    fireEvent.click(await screen.findByRole("switch", { name: "Reviews" }));

    await waitFor(() => expect(screen.getByRole("switch", { name: "Marketplace" })).toBeDisabled());
    expect(screen.getByRole("switch", { name: "Reviews" })).toBeDisabled();

    await act(async () => resolveSave(settingsPayload()));

    await waitFor(() => expect(screen.getByRole("switch", { name: "Marketplace" })).toBeEnabled());
  });

  it("shows a readable banner when the initial load fails", async () => {
    mockedFetch.mockRejectedValue(new Error("Could not reach the server"));
    render(<ModulesCard />);

    expect(await screen.findByTestId("modules-error")).toHaveTextContent(
      "Could not reach the server",
    );
    expect(screen.queryByRole("switch", { name: "Marketplace" })).not.toBeInTheDocument();
  });
});
