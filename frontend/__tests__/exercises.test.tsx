import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  formatDifficulty,
  difficultyBadgeVariant,
  formatMuscleGroup,
  formatEquipment,
  isMediaUrl,
  isVideoUrl,
  isImageUrl,
} from "@/features/exercises/components/helpers";
import { ExerciseCard } from "@/features/exercises/components/ExerciseCard";
import { ExerciseFilters } from "@/features/exercises/components/ExerciseFilters";
import { ExerciseForm } from "@/features/exercises/components/ExerciseForm";
import type { Exercise, ExerciseCategory } from "@/types/exercise";

const baseExercise: Exercise = {
  id: 1,
  name: "Barbell Bench Press",
  description: "A classic chest exercise.",
  category: 1,
  category_name: "Strength",
  muscle_groups: ["chest", "triceps", "shoulders"],
  equipment_needed: ["barbell", "bench"],
  difficulty: "intermediate",
  instructions: [
    "Lie on a flat bench.",
    "Lower the bar to your chest.",
    "Press the bar back up.",
  ],
  media_url: null,
  tips: "Keep your shoulder blades retracted.",
  contraindications: "Avoid with shoulder injuries.",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const categories: ExerciseCategory[] = [
  {
    id: 1,
    name: "Strength",
    description: "Strength training",
    slug: "strength",
    exercise_count: 10,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Cardio",
    description: "Cardiovascular",
    slug: "cardio",
    exercise_count: 5,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("Exercise helpers", () => {
  it("formats difficulty labels", () => {
    expect(formatDifficulty("beginner")).toBe("Beginner");
    expect(formatDifficulty("intermediate")).toBe("Intermediate");
    expect(formatDifficulty("advanced")).toBe("Advanced");
  });

  it("maps difficulty to badge variants", () => {
    expect(difficultyBadgeVariant("beginner")).toBe("success");
    expect(difficultyBadgeVariant("intermediate")).toBe("warning");
    expect(difficultyBadgeVariant("advanced")).toBe("danger");
  });

  it("formats muscle group names with underscores", () => {
    expect(formatMuscleGroup("lower_back")).toBe("Lower Back");
    expect(formatMuscleGroup("chest")).toBe("Chest");
  });

  it("formats equipment names", () => {
    expect(formatEquipment("squat rack")).toBe("Squat Rack");
    expect(formatEquipment("barbell")).toBe("Barbell");
  });

  it("detects media URLs", () => {
    expect(isMediaUrl("https://example.com/video.mp4")).toBe(true);
    expect(isMediaUrl(null)).toBe(false);
    expect(isMediaUrl("")).toBe(false);
    expect(isMediaUrl("not-a-url")).toBe(false);
  });

  it("detects video URLs", () => {
    expect(isVideoUrl("https://example.com/video.mp4")).toBe(true);
    expect(isVideoUrl("https://youtube.com/watch?v=abc")).toBe(true);
    expect(isVideoUrl("https://example.com/image.png")).toBe(false);
  });

  it("detects image URLs", () => {
    expect(isImageUrl("https://example.com/image.png")).toBe(true);
    expect(isImageUrl("https://example.com/photo.jpg")).toBe(true);
    expect(isImageUrl("https://example.com/video.mp4")).toBe(false);
  });
});

describe("ExerciseCard", () => {
  it("renders exercise name, category, difficulty and muscle groups", () => {
    render(<ExerciseCard exercise={baseExercise} />);
    expect(screen.getByText("Barbell Bench Press")).toBeInTheDocument();
    expect(screen.getByText("Strength")).toBeInTheDocument();
    expect(screen.getByText("Intermediate")).toBeInTheDocument();
    expect(screen.getByText("Chest")).toBeInTheDocument();
    expect(screen.getByText("Triceps")).toBeInTheDocument();
  });

  it("links to the exercise detail page", () => {
    render(<ExerciseCard exercise={baseExercise} />);
    const link = screen.getByRole("link", { name: /view details/i });
    expect(link).toHaveAttribute("href", "/exercises/1");
  });

  it("shows an edit link when canEdit is true", () => {
    render(<ExerciseCard exercise={baseExercise} canEdit />);
    expect(screen.getByRole("link", { name: /edit exercise/i })).toHaveAttribute(
      "href",
      "/exercises/1/edit",
    );
  });

  it("hides the edit link when canEdit is false", () => {
    render(<ExerciseCard exercise={baseExercise} />);
    expect(screen.queryByRole("link", { name: /edit exercise/i })).not.toBeInTheDocument();
  });

  it("shows a +more badge when there are many muscle groups", () => {
    const many = {
      ...baseExercise,
      muscle_groups: ["a", "b", "c", "d", "e", "f"],
    };
    render(<ExerciseCard exercise={many} />);
    expect(screen.getByText("+2 more")).toBeInTheDocument();
  });
});

describe("ExerciseFilters", () => {
  const noop = jest.fn();

  it("renders search input and filter dropdowns", () => {
    render(
      <ExerciseFilters categories={categories} filters={{}} onChange={noop} />,
    );
    expect(screen.getByLabelText(/search exercises/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/difficulty/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/muscle group/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/equipment/i)).toBeInTheDocument();
  });

  it("calls onChange with the search term", () => {
    const onChange = jest.fn();
    render(
      <ExerciseFilters categories={categories} filters={{}} onChange={onChange} />,
    );
    fireEvent.change(screen.getByLabelText(/search exercises/i), {
      target: { value: "squat" },
    });
    expect(onChange).toHaveBeenLastCalledWith({ search: "squat" });
  });

  it("calls onChange when a category is selected", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ExerciseFilters categories={categories} filters={{}} onChange={onChange} />,
    );
    await user.selectOptions(screen.getByLabelText(/category/i), "1");
    expect(onChange).toHaveBeenLastCalledWith({ category: "1" });
  });

  it("calls onChange when difficulty is selected", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ExerciseFilters categories={categories} filters={{}} onChange={onChange} />,
    );
    await user.selectOptions(screen.getByLabelText(/difficulty/i), "advanced");
    expect(onChange).toHaveBeenLastCalledWith({ difficulty: "advanced" });
  });

  it("shows a clear filters button when filters are active", () => {
    render(
      <ExerciseFilters
        categories={categories}
        filters={{ search: "squat" }}
        onChange={noop}
      />,
    );
    expect(screen.getByRole("button", { name: /clear filters/i })).toBeInTheDocument();
  });

  it("clears all filters when the clear button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <ExerciseFilters
        categories={categories}
        filters={{ search: "squat", difficulty: "advanced" }}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: /clear filters/i }));
    expect(onChange).toHaveBeenCalledWith({});
  });
});

describe("ExerciseForm", () => {
  it("renders all form fields", () => {
    render(
      <ExerciseForm categories={categories} onSubmit={jest.fn()} />,
    );
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/difficulty/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/media url/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tips/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/contraindications/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save exercise/i })).toBeInTheDocument();
  });

  it("shows validation errors when required fields are missing", async () => {
    const user = userEvent.setup();
    render(<ExerciseForm categories={categories} onSubmit={jest.fn()} />);
    await user.click(screen.getByRole("button", { name: /save exercise/i }));
    expect(await screen.findByText(/name is required/i)).toBeInTheDocument();
    expect(await screen.findByText(/please select a category/i)).toBeInTheDocument();
  });

  it("submits the form with the entered values", async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();
    render(<ExerciseForm categories={categories} onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/name/i), "Deadlift");
    await user.type(screen.getByLabelText(/description/i), "A compound lift.");
    await user.selectOptions(screen.getByLabelText(/category/i), "1");
    await user.selectOptions(screen.getByLabelText(/difficulty/i), "advanced");
    await user.type(screen.getByLabelText(/media url/i), "https://example.com/video.mp4");
    await user.type(screen.getByLabelText(/tips/i), "Keep the bar close.");
    await user.type(screen.getByLabelText(/contraindications/i), "Avoid with back pain.");

    await user.click(screen.getByRole("button", { name: /save exercise/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Deadlift",
          description: "A compound lift.",
          category: 1,
          difficulty: "advanced",
          media_url: "https://example.com/video.mp4",
          tips: "Keep the bar close.",
          contraindications: "Avoid with back pain.",
        }),
      );
    });
  });

  it("renders the instructions section with add-step control", () => {
    render(<ExerciseForm categories={categories} onSubmit={jest.fn()} />);
    expect(screen.getByText(/instructions/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add step/i })).toBeInTheDocument();
  });

  it("toggles muscle group chips", async () => {
    const user = userEvent.setup();
    render(<ExerciseForm categories={categories} onSubmit={jest.fn()} />);

    const chestChip = screen.getByRole("button", { name: /^chest$/i });
    expect(chestChip).toHaveAttribute("aria-pressed", "false");
    await user.click(chestChip);
    expect(chestChip).toHaveAttribute("aria-pressed", "true");
    await user.click(chestChip);
    expect(chestChip).toHaveAttribute("aria-pressed", "false");
  });

  it("shows an error alert when the API call fails", () => {
    render(
      <ExerciseForm
        categories={categories}
        onSubmit={jest.fn()}
        error={new Error("Something went wrong")}
      />,
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("disables the submit button while loading", () => {
    render(
      <ExerciseForm categories={categories} onSubmit={jest.fn()} loading />,
    );
    expect(screen.getByRole("button", { name: /save exercise/i })).toBeDisabled();
  });

  it("pre-populates fields when editing an existing exercise", () => {
    render(
      <ExerciseForm
        exercise={baseExercise}
        categories={categories}
        onSubmit={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/name/i)).toHaveValue("Barbell Bench Press");
    expect(screen.getByLabelText(/description/i)).toHaveValue(
      "A classic chest exercise.",
    );
    expect(screen.getByLabelText(/difficulty/i)).toHaveValue("intermediate");
    expect(screen.getByLabelText(/tips/i)).toHaveValue(
      "Keep your shoulder blades retracted.",
    );
  });
});
