import { render, screen } from "@testing-library/react";
import { RolesPermissions } from "@/features/settings/components/RolesPermissions";

/** Raw permission codes must never leak into the UI (issue #92). */
function expectNoRawCodes(container: HTMLElement) {
  // Permission codes look like `app.action_resource`; readable labels never do.
  expect(container.textContent).not.toMatch(/\b\w+\.\w+_\w+\b/);
}

describe("RolesPermissions (issue #92)", () => {
  it("renders a card for every displayed role with its readable label", () => {
    render(<RolesPermissions />);

    for (const [testid, label] of [
      ["role-card-gym_owner", "Gym Owner"],
      ["role-card-manager", "Manager"],
      ["role-card-trainer", "Trainer"],
      ["role-card-dietitian", "Dietitian"],
      ["role-card-customer", "Customer"],
    ] as const) {
      expect(screen.getByTestId(testid)).toBeInTheDocument();
      expect(screen.getByTestId(`role-badge-${testid.replace("role-card-", "")}`)).toHaveTextContent(label);
    }
  });

  it("presents manager permissions as readable labels grouped by area", () => {
    render(<RolesPermissions />);
    const card = screen.getByTestId("role-card-manager");

    // Group headings render…
    expect(screen.getByTestId("role-section-manager-customers")).toHaveTextContent("Customers");
    expect(screen.getByTestId("role-section-manager-payments")).toHaveTextContent("Payments");
    // …and the chips carry labels, not codes.
    expect(card).toHaveTextContent("View customers");
    expect(card).toHaveTextContent("Record payments");
    expectNoRawCodes(card);
  });

  it("shows the full-access note for the owner instead of per-permission chips", () => {
    render(<RolesPermissions />);
    const card = screen.getByTestId("role-card-gym_owner");

    expect(screen.getByTestId("role-full-access-gym_owner")).toHaveTextContent(
      /can do everything in the dashboard/i,
    );
    expect(screen.getByTestId("role-summary-gym_owner")).toHaveTextContent("Full access");
    expectNoRawCodes(card);
  });

  it("summarizes narrower roles with a permission + area count", () => {
    render(<RolesPermissions />);
    const summary = screen.getByTestId("role-summary-dietitian");
    // Dietitian: 4 permissions (customers + 3 diet) across 2 areas.
    expect(summary).toHaveTextContent("4 permissions across 2 areas");
  });

  it("never renders a raw permission code anywhere on the page", () => {
    const { container } = render(<RolesPermissions />);
    expectNoRawCodes(container);
  });
});
