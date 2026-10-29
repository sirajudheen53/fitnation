import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { GymCodeCard } from "@/features/settings/components/GymCodeCard";
import { fetchTenant, errorMessage } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  fetchTenant: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedFetchTenant = fetchTenant as jest.Mock;
const mockedErrorMessage = errorMessage as jest.Mock;
const writeText = jest.fn().mockResolvedValue(undefined);

beforeAll(() => {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
});

beforeEach(() => {
  jest.clearAllMocks();
  writeText.mockResolvedValue(undefined);
  mockedErrorMessage.mockImplementation((err: unknown) =>
    err instanceof Error ? err.message : "error",
  );
});

describe("GymCodeCard", () => {
  it("shows the gym code returned by /tenants/me/", async () => {
    mockedFetchTenant.mockResolvedValue({ gym_code: "H4SHFIT" });
    render(<GymCodeCard />);
    expect(await screen.findByTestId("gym-code-value")).toHaveTextContent("H4SHFIT");
    expect(screen.getByTestId("gym-code-card")).toHaveTextContent(/specify their gym/i);
  });

  it("tells owners the code is how first-time members sign in (#87)", async () => {
    mockedFetchTenant.mockResolvedValue({ gym_code: "H4SHFIT" });
    render(<GymCodeCard />);
    expect(await screen.findByTestId("gym-code-help")).toHaveTextContent(
      /first-time members type this code/i,
    );
  });

  it("treats a missing gym_code as absent instead of rendering 'null'", async () => {
    mockedFetchTenant.mockResolvedValue({});
    render(<GymCodeCard />);
    expect(await screen.findByTestId("gym-code-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("gym-code-value")).not.toBeInTheDocument();
  });

  it("copies the code to the clipboard and toasts on success", async () => {
    mockedFetchTenant.mockResolvedValue({ gym_code: "H4SHFIT" });
    render(<GymCodeCard />);

    fireEvent.click(await screen.findByTestId("gym-code-copy"));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("H4SHFIT"));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Gym code copied"));
  });

  it("toasts an error when the clipboard write fails", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    mockedFetchTenant.mockResolvedValue({ gym_code: "H4SHFIT" });
    render(<GymCodeCard />);

    fireEvent.click(await screen.findByTestId("gym-code-copy"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Copy failed — select the code manually"),
    );
  });

  it("surfaces a readable error when the tenant fetch fails", async () => {
    mockedFetchTenant.mockRejectedValue(new Error("Network down"));
    render(<GymCodeCard />);
    expect(await screen.findByTestId("gym-code-error")).toHaveTextContent("Network down");
  });
});
