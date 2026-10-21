import { render, screen, within } from "@testing-library/react";
import HomePage from "@/app/page";
import SignUpPage from "@/app/signup/page";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

describe("public pages legal footer", () => {
  it("landing page footer links to privacy policy and account deletion", () => {
    render(<HomePage />);

    const privacyLink = screen.getByRole("link", { name: /privacy policy/i });
    expect(privacyLink).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: /delete account data/i })).toHaveAttribute(
      "href",
      "/data-deletion"
    );
  });

  it("signup page points new users at the privacy policy and deletion page", () => {
    render(<SignUpPage />);

    expect(screen.getByText(/terms of service and/i)).toBeInTheDocument();
    const privacyLink = screen.getByRole("link", { name: /^privacy policy$/i });
    expect(privacyLink).toHaveAttribute("href", "/privacy");
    expect(
      within(privacyLink.closest("p")!).getByRole("link", { name: /delete account data/i })
    ).toHaveAttribute("href", "/data-deletion");
  });
});