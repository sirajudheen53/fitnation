import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  getCategoryLabel,
  getFeedbackAuthorName,
  hasResponse,
  formatFeedbackDate,
  renderStars,
  getRatingVariant,
  getResponseVariant,
} from "@/features/feedback/components/feedbackHelpers";
import { FeedbackForm } from "@/features/feedback/components/FeedbackForm";
import { FeedbackTable } from "@/features/feedback/components/FeedbackTable";
import type { Feedback } from "@/types/feedback";

const baseFeedback: Feedback = {
  id: 1,
  customer: 10,
  customer_name: "Arjun Kumar",
  rating: 5,
  category: "workout",
  comment: "Great workout session!",
  is_anonymous: false,
  response: null,
  response_by: null,
  response_by_name: null,
  response_at: null,
  created_at: "2026-08-01T10:00:00Z",
};

describe("feedbackHelpers", () => {
  it("returns the correct label for each category", () => {
    expect(getCategoryLabel("workout")).toBe("Workout");
    expect(getCategoryLabel("diet")).toBe("Diet");
    expect(getCategoryLabel("trainer")).toBe("Trainer");
    expect(getCategoryLabel("facility")).toBe("Facility");
    expect(getCategoryLabel("app")).toBe("App");
  });

  it("shows the customer name when not anonymous", () => {
    expect(getFeedbackAuthorName(baseFeedback)).toBe("Arjun Kumar");
  });

  it("shows Anonymous when is_anonymous is true", () => {
    expect(getFeedbackAuthorName({ ...baseFeedback, is_anonymous: true })).toBe(
      "Anonymous",
    );
  });

  it("falls back to Customer when no name is present", () => {
    expect(
      getFeedbackAuthorName({ ...baseFeedback, customer_name: null }),
    ).toBe("Customer");
  });

  it("detects whether a response exists", () => {
    expect(hasResponse(baseFeedback)).toBe(false);
    expect(hasResponse({ ...baseFeedback, response: "Thanks!" })).toBe(true);
    expect(hasResponse({ ...baseFeedback, response: "   " })).toBe(false);
  });

  it("formats an ISO date to a locale string", () => {
    const formatted = formatFeedbackDate("2026-08-01T10:00:00Z");
    expect(formatted).not.toBe("—");
    expect(formatted).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns an em dash for null dates", () => {
    expect(formatFeedbackDate(null)).toBe("—");
  });

  it("renders the correct number of filled stars", () => {
    expect(renderStars(5)).toBe("★★★★★");
    expect(renderStars(3)).toBe("★★★☆☆");
    expect(renderStars(1)).toBe("★☆☆☆☆");
  });

  it("clamps out-of-range ratings", () => {
    expect(renderStars(0)).toBe("★☆☆☆☆");
    expect(renderStars(9)).toBe("★★★★★");
  });

  it("maps ratings to badge variants", () => {
    expect(getRatingVariant(5)).toBe("success");
    expect(getRatingVariant(4)).toBe("success");
    expect(getRatingVariant(3)).toBe("warning");
    expect(getRatingVariant(2)).toBe("danger");
    expect(getRatingVariant(1)).toBe("danger");
  });

  it("maps response status to badge variants", () => {
    expect(getResponseVariant(baseFeedback)).toBe("default");
    expect(getResponseVariant({ ...baseFeedback, response: "ok" })).toBe("success");
  });
});

describe("FeedbackForm", () => {
  it("renders the form fields", () => {
    render(<FeedbackForm onSubmit={jest.fn()} />);
    expect(screen.getByRole("button", { name: "5 stars" })).toBeInTheDocument();
    expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/your feedback/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit feedback/i })).toBeInTheDocument();
  });

  it("shows validation errors when required fields are missing", async () => {
    const user = userEvent.setup();
    render(<FeedbackForm onSubmit={jest.fn()} />);
    await user.click(screen.getByRole("button", { name: /submit feedback/i }));
    expect(await screen.findByText(/please select a rating/i)).toBeInTheDocument();
  });

  it("submits the form with the selected values", async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    render(<FeedbackForm onSubmit={onSubmit} />);

    // Select 4 stars
    await user.click(screen.getByRole("button", { name: "4 stars" }));

    // Select category
    await user.selectOptions(screen.getByLabelText(/category/i), "trainer");

    // Type comment
    await user.type(screen.getByLabelText(/your feedback/i), "Amazing trainer!");

    // Toggle anonymous
    await user.click(screen.getByLabelText(/submit anonymously/i));

    await user.click(screen.getByRole("button", { name: /submit feedback/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        rating: 4,
        category: "trainer",
        comment: "Amazing trainer!",
        is_anonymous: true,
      });
    });
  });

  it("shows an error alert when the API call fails", async () => {
    const user = userEvent.setup();
    render(
      <FeedbackForm
        onSubmit={jest.fn()}
        error={new Error("Something went wrong")}
      />,
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("disables the submit button while loading", () => {
    render(<FeedbackForm onSubmit={jest.fn()} loading />);
    expect(screen.getByRole("button", { name: /submit feedback/i })).toBeDisabled();
  });
});

describe("FeedbackTable", () => {
  const items: Feedback[] = [
    baseFeedback,
    {
      ...baseFeedback,
      id: 2,
      customer_name: null,
      is_anonymous: true,
      rating: 2,
      category: "facility",
      comment: "Equipment needs maintenance.",
      response: "We will fix it soon.",
      response_at: "2026-08-02T09:00:00Z",
    },
  ];

  it("renders feedback items with author, rating, category and comment", () => {
    render(<FeedbackTable feedback={items} onRespond={jest.fn()} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("Anonymous")).toBeInTheDocument();
    expect(screen.getByText("Great workout session!")).toBeInTheDocument();
    expect(screen.getByText("Equipment needs maintenance.")).toBeInTheDocument();
    expect(screen.getByText("Workout")).toBeInTheDocument();
    expect(screen.getByText("Facility")).toBeInTheDocument();
  });

  it("shows the existing response for responded feedback", () => {
    render(<FeedbackTable feedback={items} onRespond={jest.fn()} />);
    expect(screen.getByText("We will fix it soon.")).toBeInTheDocument();
  });

  it("shows an empty state when there is no feedback", () => {
    render(<FeedbackTable feedback={[]} onRespond={jest.fn()} />);
    expect(screen.getByText(/no feedback found/i)).toBeInTheDocument();
  });

  it("allows responding to feedback inline", async () => {
    const user = userEvent.setup();
    const onRespond = jest.fn().mockResolvedValue(undefined);
    render(<FeedbackTable feedback={[baseFeedback]} onRespond={onRespond} />);

    await user.click(screen.getByRole("button", { name: /respond/i }));
    const textarea = screen.getByPlaceholderText(/write a response/i);
    await user.type(textarea, "Thanks for the feedback!");
    await user.click(screen.getByRole("button", { name: /submit response/i }));

    await waitFor(() => {
      expect(onRespond).toHaveBeenCalledWith(
        baseFeedback,
        "Thanks for the feedback!",
      );
    });
  });

  it("does not submit an empty response", async () => {
    const user = userEvent.setup();
    const onRespond = jest.fn().mockResolvedValue(undefined);
    render(<FeedbackTable feedback={[baseFeedback]} onRespond={onRespond} />);

    await user.click(screen.getByRole("button", { name: /respond/i }));
    const submit = screen.getByRole("button", { name: /submit response/i });
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(onRespond).not.toHaveBeenCalled();
  });
});
