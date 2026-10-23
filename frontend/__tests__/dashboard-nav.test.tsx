import { fireEvent, render, screen } from "@testing-library/react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { setStoredUser, setToken, type StoredUser } from "@/lib/auth";

const mockPathname = jest.fn().mockReturnValue("/dashboard");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() }),
  usePathname: () => mockPathname(),
}));

const ownerUser: StoredUser = {
  id: 2,
  email: "owner@irontemple.com",
  name: "Gym Owner",
  role: "gym_owner",
  tenant_id: 7,
  tenant_name: "Iron Temple Fitness",
  is_owner: true,
};

const platformAdmin: StoredUser = {
  id: 1,
  email: "ops@fitnation.app",
  name: "Platform Admin",
  role: "platform_admin",
  tenant_id: null,
  tenant_name: null,
  is_owner: false,
};

beforeEach(() => {
  jest.clearAllMocks();
  mockPathname.mockReturnValue("/dashboard");
  localStorage.clear();
  setToken("token-1");
  setStoredUser(ownerUser);
});

afterEach(() => {
  localStorage.clear();
});

describe("DashboardLayout sidebar sections (issue #62)", () => {
  it("renders the five labeled sections for a gym owner", () => {
    render(
      <DashboardLayout title="Dashboard">
        <p>content</p>
      </DashboardLayout>,
    );

    for (const label of ["Operations", "Trainers", "Programs", "Growth", "Settings"]) {
      // selector avoids matching the same-named nav link ("Trainers", "Settings").
      expect(screen.getByText(label, { selector: "div" })).toBeInTheDocument();
    }
  });

  it("keeps every nav item reachable under its section", () => {
    render(
      <DashboardLayout title="Dashboard">
        <p>content</p>
      </DashboardLayout>,
    );

    const itemsInSection: Record<string, string[]> = {
      Operations: ["/dashboard", "/branches", "/customers", "/memberships", "/payments", "/attendance", "/devices"],
      Trainers: ["/trainers", "/pt-sessions", "/trainers/performance"],
      Programs: ["/workouts", "/diet", "/nutrition", "/ai-coach"],
      Growth: ["/inventory", "/marketplace", "/reviews", "/feedback", "/analytics"],
      Settings: ["/notifications/settings", "/settings"],
    };

    for (const [section, hrefs] of Object.entries(itemsInSection)) {
      // The label is a div; the same-named nav link is an <a>, so the
      // selector disambiguates (e.g. "Trainers" label vs "Trainers" link).
      const sectionEl = screen.getByText(section, { selector: "div" });
      const sectionContainer = sectionEl.parentElement;
      expect(sectionContainer).not.toBeNull();

      for (const href of hrefs) {
        const link = screen.getByRole("link", { name: labelFor(href) });
        expect(link).toHaveAttribute("href", href);
        expect(sectionContainer!).toContainElement(link);
      }
    }
  });

  it("marks the active item with aria-current", () => {
    mockPathname.mockReturnValue("/trainers/performance");
    render(
      <DashboardLayout title="Trainer Performance">
        <p>content</p>
      </DashboardLayout>,
    );

    expect(screen.getByRole("link", { name: "Trainer Performance" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("shows platform admins only the grouped Admin section", () => {
    setStoredUser(platformAdmin);
    render(
      <DashboardLayout title="Gyms">
        <p>content</p>
      </DashboardLayout>,
    );

    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gyms" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("link", { name: "Plans" })).toHaveAttribute("href", "/admin/plans");
    expect(screen.getByRole("link", { name: "Onboard Gym" })).toHaveAttribute("href", "/admin/onboard");
    expect(screen.queryByText("Operations")).toBeNull();
    expect(screen.queryByRole("link", { name: "Dashboard" })).toBeNull();
  });

  it("renders the same grouping in the mobile drawer", () => {
    render(
      <DashboardLayout title="Dashboard">
        <p>content</p>
      </DashboardLayout>,
    );

    expect(screen.getAllByText("Operations", { selector: "div" })).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));

    // Desktop sidebar + mobile drawer both render the grouped nav.
    for (const label of ["Operations", "Trainers", "Programs", "Growth", "Settings"]) {
      expect(screen.getAllByText(label, { selector: "div" })).toHaveLength(2);
    }
    expect(screen.getAllByRole("link", { name: "Customers" })).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Feedback" })).toHaveLength(2);
  });
});

function labelFor(href: string): string {
  const labels: Record<string, string> = {
    "/dashboard": "Dashboard",
    "/branches": "Branches",
    "/customers": "Customers",
    "/memberships": "Memberships",
    "/payments": "Payments",
    "/attendance": "Attendance",
    "/devices": "Access Devices",
    "/trainers": "Trainers",
    "/pt-sessions": "PT Sessions",
    "/trainers/performance": "Trainer Performance",
    "/workouts": "Workouts",
    "/diet": "Diets",
    "/nutrition": "Nutrition",
    "/ai-coach": "AI Coach",
    "/inventory": "Inventory",
    "/marketplace": "Marketplace",
    "/reviews": "Reviews",
    "/feedback": "Feedback",
    "/analytics": "Analytics",
    "/notifications/settings": "Notifications",
    "/settings": "Settings",
  };
  const label = labels[href];
  if (!label) throw new Error(`No label mapped for ${href}`);
  return label;
}
