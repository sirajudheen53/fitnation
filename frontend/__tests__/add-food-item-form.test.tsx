import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AddFoodItemForm } from "@/features/diet/components/AddFoodItemForm";
import type { FoodItemFormData } from "@/types/diet";

describe("AddFoodItemForm", () => {
  const fillValidForm = () => {
    fireEvent.change(screen.getByLabelText("Dish name"), {
      target: { value: "Grilled Paneer Salad" },
    });
    fireEvent.change(screen.getByLabelText("Serving size"), {
      target: { value: "1 bowl (250g)" },
    });
    fireEvent.change(screen.getByLabelText("Calories (kcal)"), {
      target: { value: "320" },
    });
    fireEvent.change(screen.getByLabelText("Protein (g)"), {
      target: { value: "18" },
    });
    fireEvent.change(screen.getByLabelText("Carbs (g)"), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText("Fat (g)"), {
      target: { value: "22" },
    });
  };

  it("submits a dish payload with macros and tags", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0] as FoodItemFormData;
    expect(payload.name).toBe("Grilled Paneer Salad");
    expect(payload.serving_size).toBe("1 bowl (250g)");
    expect(payload.calories).toBe(320);
    expect(payload.protein).toBe(18);
    expect(payload.carbs).toBe(12);
    expect(payload.fat).toBe(22);
    expect(payload.is_dish).toBe(true);
    expect(payload.meal_type).toBeNull();
    expect(payload.is_veg).toBe(true);
  });

  it("sends the selected meal slot", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fillValidForm();
    fireEvent.change(screen.getByLabelText("Meal slot (optional)"), {
      target: { value: "dinner" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].meal_type).toBe("dinner");
  });

  it("rejects negative nutrition values without submitting", async () => {
    const onSubmit = jest.fn();
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fillValidForm();
    fireEvent.change(screen.getByLabelText("Protein (g)"), {
      target: { value: "-5" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    expect(
      await screen.findByText("Nutrition values cannot be negative."),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("requires a dish name", async () => {
    const onSubmit = jest.fn();
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Calories (kcal)"), {
      target: { value: "320" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    expect(
      await screen.findByText("Dish name is required."),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("treats cleared nutrition fields as zero", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fillValidForm();
    // Number inputs sanitize invalid/blank values to "" before JS sees them.
    fireEvent.change(screen.getByLabelText("Fiber (g)"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].fiber).toBe(0);
  });

  it("toggles the vegetarian flag off", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(<AddFoodItemForm onSubmit={onSubmit} />);

    fillValidForm();
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(screen.getByRole("button", { name: /add dish/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].is_veg).toBe(false);
  });

  it("shows a Cancel button only when onCancel is provided", () => {
    render(<AddFoodItemForm onSubmit={jest.fn()} />);
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();

    render(<AddFoodItemForm onSubmit={jest.fn()} onCancel={jest.fn()} />);
    expect(
      screen.getByRole("button", { name: /cancel/i }),
    ).toBeInTheDocument();
  });
});
