import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MembershipPlanForm } from "@/features/memberships/components/MembershipPlanForm";
import { errorMessage } from "@/lib/api";
import type { MembershipPlan } from "@/types/membership";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
}));

const mockedErrorMessage = errorMessage as jest.Mock;

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
  id: 1,
  name: "Gold",
  price: "1999.00",
  duration_days: 30,
  plan_type: "monthly",
  description: null,
  is_active: true,
  includes_app_access: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

function selectPlanType(value: string) {
  fireEvent.change(screen.getByLabelText("Plan type"), { target: { value } });
}

async function submitForm() {
  fireEvent.click(screen.getByRole("button", { name: "Save plan" }));
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("MembershipPlanForm", () => {
  it("offers the full plan type union accepted by the backend", () => {
    render(<MembershipPlanForm onSubmit={jest.fn()} />);
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual([
      "Monthly",
      "Quarterly",
      "Half-yearly",
      "Yearly",
      "Personal Training",
      "Trial",
    ]);
  });

  it.each(["pt", "trial"] as const)(
    "submits an existing %s plan without client-side rejection",
    async (planType) => {
      const onSubmit = jest.fn();
      render(
        <MembershipPlanForm
          plan={plan({ plan_type: planType, duration_days: 45 })}
          onSubmit={onSubmit}
        />,
      );
      await submitForm();
      await waitFor(() =>
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ plan_type: planType, duration_days: 45 }),
        ),
      );
    },
  );

  it.each([
    ["monthly", 30],
    ["quarterly", 90],
    ["half_yearly", 180],
    ["yearly", 365],
  ])("prefills duration to %s days when the user picks %s", (planType, expected) => {
    render(<MembershipPlanForm onSubmit={jest.fn()} />);
    selectPlanType(planType);
    expect(screen.getByLabelText("Duration (days)")).toHaveValue(expected);
  });

  it("leaves duration untouched when the user picks pt or trial", () => {
    render(
      <MembershipPlanForm plan={plan({ plan_type: "monthly", duration_days: 45 })} onSubmit={jest.fn()} />,
    );
    selectPlanType("pt");
    expect(screen.getByLabelText("Duration (days)")).toHaveValue(45);
    selectPlanType("trial");
    expect(screen.getByLabelText("Duration (days)")).toHaveValue(45);
  });

  it("does not prefill duration when loading a plan (reset only)", () => {
    render(
      <MembershipPlanForm
        plan={plan({ plan_type: "quarterly", duration_days: 100 })}
        onSubmit={jest.fn()}
      />,
    );
    expect(screen.getByLabelText("Duration (days)")).toHaveValue(100);
  });

  it("shows a validation error and skips submit when duration is cleared", async () => {
    const onSubmit = jest.fn();
    render(<MembershipPlanForm onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Duration (days)"), { target: { value: "" } });
    await submitForm();
    expect(await screen.findByText("Duration must be positive")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(mockedErrorMessage).not.toHaveBeenCalled();
  });

  // ── FBOS-011 F1: "Includes app access" toggle ────────────────────

  it("defaults the app-access toggle to ON with the customer-facing helper line", () => {
    render(<MembershipPlanForm onSubmit={jest.fn()} />);
    const toggle = screen.getByLabelText(/Includes app access/i);
    expect(toggle).toBeChecked();
    expect(
      screen.getByText(/Members on this plan can use the FitNation mobile app/i),
    ).toBeInTheDocument();
  });

  it("submits includes_app_access: true by default (launch default per ADR-003)", async () => {
    const onSubmit = jest.fn();
    render(
      <MembershipPlanForm
        defaultValues={{ name: "Gold", price: 1999, duration_days: 30 }}
        onSubmit={onSubmit}
      />,
    );
    await submitForm();
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ includes_app_access: true })),
    );
  });

  it("round-trips includes_app_access when editing a plan and submits the un-toggled value", async () => {
    const onSubmit = jest.fn();
    render(<MembershipPlanForm plan={plan({ includes_app_access: false })} onSubmit={onSubmit} />);
    const toggle = screen.getByLabelText(/Includes app access/i);
    expect(toggle).not.toBeChecked();
    await submitForm();
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ includes_app_access: false })),
    );
  });

  it("sends includes_app_access: false when the user turns a defaulted-on toggle off", async () => {
    const onSubmit = jest.fn();
    render(
      <MembershipPlanForm
        defaultValues={{ name: "Gold", price: 1999, duration_days: 30 }}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByLabelText(/Includes app access/i));
    await submitForm();
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ includes_app_access: false })),
    );
  });

  it("treats a missing includes_app_access on a loaded plan as ON (pre-feature payloads)", () => {
    render(<MembershipPlanForm plan={plan({ includes_app_access: undefined })} onSubmit={jest.fn()} />);
    expect(screen.getByLabelText(/Includes app access/i)).toBeChecked();
  });
});
