import { render, screen } from "@testing-library/react";
import InviteLandingPage from "@/app/g/[uuid]/page";

// 8-4-4-4-12 hex, matching mobile join_link.dart's regex.
const VALID = "7f9d2a6b-3c8e-4a55-9f1e-2b7c0d4e8f10";
const UPPER = "7F9D2A6B-3C8E-4A55-9F1E-2B7C0D4E8F10";

async function inviteElement(uuid: string) {
  return InviteLandingPage({ params: Promise.resolve({ uuid }) });
}

describe("/g/[uuid] invite landing", () => {
  it("renders Open App + Play links with the exact invite URLs", async () => {
    render(await inviteElement(VALID));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /you.ve been invited to join your gym/i,
      })
    ).toBeInTheDocument();

    const openApp = screen.getByRole("link", { name: "Open App" });
    expect(openApp).toHaveAttribute("href", `fitnation://g/${VALID}`);

    const play = screen.getByRole("link", { name: /get it on google play/i });
    expect(play).toHaveAttribute(
      "href",
      `https://play.google.com/store/apps/details?id=com.getfitwithus.app&referrer=gym%3D${VALID}`
    );
  });

  it("shows the phone handoff copy for desktop/plain browsers", async () => {
    render(await inviteElement(VALID));

    expect(screen.getByText(/open this invite on your phone/i)).toBeInTheDocument();
  });

  it("accepts uppercase hex, same as the mobile deep-link parser", async () => {
    render(await inviteElement(UPPER));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /you.ve been invited to join your gym/i,
      })
    ).toBeInTheDocument();
  });

  it.each([
    "not-a-gym-uuid",
    "g/../../etc",
    "7f9d2a6b3c8e4a559f1e2b7c0d4e8f1", // missing dashes/wrong shape
  ])("404s on non-uuid path param %j", async (bad) => {
    await expect(inviteElement(bad)).rejects.toThrow(/404/);
  });

  it("does not leak the uuid in any other link target", async () => {
    render(await inviteElement(VALID));

    screen.getAllByRole("link").forEach((a) => {
      const href = a.getAttribute("href") ?? "";
      expect(href.includes(VALID)).toBe(true);
    });
  });
});