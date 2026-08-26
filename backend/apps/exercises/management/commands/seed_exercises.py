"""Seed the exercise library with common exercises.

Usage::

    python manage.py seed_exercises [--tenant <tenant_id>] [--reset]

Populates 50+ common exercises across Strength, Cardio, Flexibility, and
Mobility categories. Exercises are tenant-scoped.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.exercises.models import Exercise, ExerciseCategory
from apps.tenants.models import Tenant

_EXERCISE_DATA = [
    # ── Strength ────────────────────────────────────────────────────────────────
    {
        "name": "Barbell Bench Press",
        "category": "strength",
        "muscle_groups": ["chest", "triceps", "shoulders"],
        "equipment_needed": ["barbell", "bench"],
        "difficulty": "intermediate",
        "instructions": [
            "Lie on a flat bench with feet planted on the floor.",
            "Grip the barbell slightly wider than shoulder-width.",
            "Lower the bar to your mid-chest under control.",
            "Press the bar back up until your arms are extended.",
        ],
        "tips": "Keep your shoulder blades retracted and back arched slightly.",
        "contraindications": "Avoid if you have a recent shoulder or wrist injury.",
    },
    {
        "name": "Barbell Back Squat",
        "category": "strength",
        "muscle_groups": ["quadriceps", "hamstrings", "glutes", "core"],
        "equipment_needed": ["barbell", "squat rack"],
        "difficulty": "intermediate",
        "instructions": [
            "Rest the bar on your upper traps and unrack it.",
            "Feet shoulder-width apart, toes slightly out.",
            "Squat down keeping your chest up until thighs are parallel.",
            "Drive through the heels to stand back up.",
        ],
        "tips": "Keep knees tracking over toes and brace your core throughout.",
        "contraindications": "Avoid if you have significant knee or lower-back issues.",
    },
    {
        "name": "Deadlift",
        "category": "strength",
        "muscle_groups": ["hamstrings", "glutes", "lower_back", "traps"],
        "equipment_needed": ["barbell"],
        "difficulty": "advanced",
        "instructions": [
            "Stand with feet hip-width apart over the bar.",
            "Hinge down and grip the bar just outside your legs.",
            "Flatten your back and brace your core.",
            "Stand up by driving through the floor and extending the hips.",
        ],
        "tips": "Keep the bar close to your body and avoid rounding the lower back.",
        "contraindications": "Avoid with acute lower back pain or herniated discs.",
    },
    {
        "name": "Overhead Press",
        "category": "strength",
        "muscle_groups": ["shoulders", "triceps", "core"],
        "equipment_needed": ["barbell"],
        "difficulty": "intermediate",
        "instructions": [
            "Grip the bar at shoulder height, hands slightly outside shoulders.",
            "Brace your core and glutes.",
            "Press the bar overhead until arms are locked out.",
            "Lower back down to shoulder height with control.",
        ],
        "tips": "Avoid arching the lower back; press straight up.",
    },
    {
        "name": "Bent-Over Barbell Row",
        "category": "strength",
        "muscle_groups": ["back", "lats", "biceps", "rear_delts"],
        "equipment_needed": ["barbell"],
        "difficulty": "intermediate",
        "instructions": [
            "Hinge forward with a flat back, bar hanging at knee height.",
            "Pull the bar to your lower chest.",
            "Squeeze the shoulder blades at the top.",
            "Lower the bar with control.",
        ],
        "tips": "Keep a neutral spine and avoid jerky momentum.",
    },
    {
        "name": "Pull-Up",
        "category": "strength",
        "muscle_groups": ["back", "lats", "biceps"],
        "equipment_needed": ["pull-up bar"],
        "difficulty": "advanced",
        "instructions": [
            "Hang from the bar with an overhand grip, arms extended.",
            "Pull your chin over the bar by driving elbows down.",
            "Pause briefly at the top.",
            "Lower back to a full hang with control.",
        ],
        "tips": "Use a resistance band to assist if you cannot yet complete full reps.",
        "contraindications": "Avoid if you have rotator cuff or shoulder instability.",
    },
    {
        "name": "Dumbbell Shoulder Press",
        "category": "strength",
        "muscle_groups": ["shoulders", "triceps"],
        "equipment_needed": ["dumbbells"],
        "difficulty": "beginner",
        "instructions": [
            "Hold a dumbbell in each hand at shoulder height.",
            "Press both dumbbells overhead until arms are extended.",
            "Lower back down to shoulder height.",
        ],
    },
    {
        "name": "Dumbbell Bicep Curl",
        "category": "strength",
        "muscle_groups": ["biceps", "forearms"],
        "equipment_needed": ["dumbbells"],
        "difficulty": "beginner",
        "instructions": [
            "Stand holding dumbbells with palms facing forward.",
            "Curl the dumbbells toward your shoulders.",
            "Squeeze the biceps at the top.",
            "Lower back down under control.",
        ],
    },
    {
        "name": "Triceps Pushdown",
        "category": "strength",
        "muscle_groups": ["triceps"],
        "equipment_needed": ["cable machine", "rope attachment"],
        "difficulty": "beginner",
        "instructions": [
            "Stand facing a cable machine set at chest height.",
            "Grip the rope and keep elbows pinned to your sides.",
            "Extend your elbows to push the rope down.",
            "Return to the start under control.",
        ],
    },
    {
        "name": "Lat Pulldown",
        "category": "strength",
        "muscle_groups": ["back", "lats", "biceps"],
        "equipment_needed": ["cable machine"],
        "difficulty": "beginner",
        "instructions": [
            "Sit at the lat pulldown machine and grip the bar wide.",
            "Pull the bar down to your upper chest.",
            "Drive elbows down and squeeze the lats.",
            "Let the bar rise slowly back to the start.",
        ],
    },
    {
        "name": "Dumbbell Lateral Raise",
        "category": "strength",
        "muscle_groups": ["shoulders"],
        "equipment_needed": ["dumbbells"],
        "difficulty": "beginner",
        "instructions": [
            "Stand holding light dumbbells at your sides.",
            "Raise the arms out to the sides to shoulder height.",
            "Pause briefly, then lower with control.",
        ],
    },
    {
        "name": "Leg Press",
        "category": "strength",
        "muscle_groups": ["quadriceps", "glutes", "hamstrings"],
        "equipment_needed": ["leg press machine"],
        "difficulty": "beginner",
        "instructions": [
            "Sit in the leg press with feet shoulder-width on the platform.",
            "Lower the platform by bending your knees toward your chest.",
            "Press the platform away by extending your legs.",
            "Do not lock out the knees at the top.",
        ],
    },
    {
        "name": "Romanian Deadlift",
        "category": "strength",
        "muscle_groups": ["hamstrings", "glutes", "lower_back"],
        "equipment_needed": ["dumbbells", "barbell"],
        "difficulty": "intermediate",
        "instructions": [
            "Stand with a slight bend in the knees holding the load.",
            "Hinge at the hips and push them back.",
            "Lower the weight along your legs until you feel a hamstring stretch.",
            "Return to standing by driving the hips forward.",
        ],
    },
    {
        "name": "Goblet Squat",
        "category": "strength",
        "muscle_groups": ["quadriceps", "glutes", "core"],
        "equipment_needed": ["dumbbell", "kettlebell"],
        "difficulty": "beginner",
        "instructions": [
            "Hold a dumbbell vertically against your chest.",
            "Squat down keeping your chest up.",
            "Drive through the heels to stand back up.",
        ],
    },
    {
        "name": "Push-Up",
        "category": "strength",
        "muscle_groups": ["chest", "triceps", "shoulders", "core"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Start in a plank position with hands under shoulders.",
            "Lower your chest toward the floor.",
            "Press back up to the start.",
        ],
    },
    {
        "name": "Dumbbell Chest Fly",
        "category": "strength",
        "muscle_groups": ["chest", "shoulders"],
        "equipment_needed": ["dumbbells", "bench"],
        "difficulty": "beginner",
        "instructions": [
            "Lie on a flat bench holding dumbbells above your chest.",
            "Open the arms out wide in a slight arc.",
            "Squeeze the chest to bring the dumbbells back together.",
        ],
    },
    {
        "name": "Hip Thrust",
        "category": "strength",
        "muscle_groups": ["glutes", "hamstrings"],
        "equipment_needed": ["barbell", "bench"],
        "difficulty": "intermediate",
        "instructions": [
            "Sit with your upper back against a bench and the bar over your hips.",
            "Drive through the heels to raise your hips.",
            "Squeeze the glutes at the top.",
            "Lower back down with control.",
        ],
    },
    {
        "name": "Calf Raise",
        "category": "strength",
        "muscle_groups": ["calves"],
        "equipment_needed": ["leg press machine", "step"],
        "difficulty": "beginner",
        "instructions": [
            "Stand with the balls of your feet on an elevated edge.",
            "Raise your heels as high as possible.",
            "Lower slowly below the edge for a stretch.",
        ],
    },
    {
        "name": "Face Pull",
        "category": "strength",
        "muscle_groups": ["rear_delts", "rotator_cuff", "traps"],
        "equipment_needed": ["cable machine"],
        "difficulty": "beginner",
        "instructions": [
            "Attach a rope to a cable at upper chest height.",
            "Pull the rope toward your face, separating the ends.",
            "Squeeze the rear delts at the peak.",
            "Return with control.",
        ],
    },
    {
        "name": "Plank",
        "category": "strength",
        "muscle_groups": ["core", "shoulders", "glutes"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Hold a forearm plank with a straight line from head to heels.",
            "Brace your core and glutes.",
            "Hold for the prescribed time.",
        ],
    },
    {
        "name": "Incline Dumbbell Press",
        "category": "strength",
        "muscle_groups": ["chest", "shoulders", "triceps"],
        "equipment_needed": ["dumbbells", "bench"],
        "difficulty": "beginner",
        "instructions": [
            "Set the bench to a 30-45 degree incline.",
            "Press the dumbbells from shoulder height to above the chest.",
            "Lower back under control.",
        ],
    },
    {
        "name": "Seated Cable Row",
        "category": "strength",
        "muscle_groups": ["back", "lats", "biceps"],
        "equipment_needed": ["cable machine"],
        "difficulty": "beginner",
        "instructions": [
            "Sit at the row station and grab the handle.",
            "Pull the handle to your midsection with a proud chest.",
            "Squeeze the back, then return with control.",
        ],
    },
    {
        "name": "Dumbbell Romanian Deadlift",
        "category": "strength",
        "muscle_groups": ["hamstrings", "glutes"],
        "equipment_needed": ["dumbbells"],
        "difficulty": "beginner",
        "instructions": [
            "Hold a dumbbell in each hand in front of your thighs.",
            "Hinge at the hips, lowering the weights along your legs.",
            "Return to standing by squeezing the glutes.",
        ],
    },
    {
        "name": "Kettlebell Swing",
        "category": "strength",
        "muscle_groups": ["glutes", "hamstrings", "core", "shoulders"],
        "equipment_needed": ["kettlebell"],
        "difficulty": "intermediate",
        "instructions": [
            "Hinge and hold the kettlebell between your legs.",
            "Explosively drive the hips forward to swing the bell to chest height.",
            "Let it swing back between your legs and repeat.",
        ],
        "contraindications": "Avoid with low-back pain; use strict hip-hinge form.",
    },
    {
        "name": "Step-Up",
        "category": "strength",
        "muscle_groups": ["quadriceps", "glutes", "hamstrings"],
        "equipment_needed": ["box", "platform"],
        "difficulty": "beginner",
        "instructions": [
            "Place one foot fully on a sturdy box.",
            "Drive through that leg to step up onto the box.",
            "Step back down with control and repeat on the other leg.",
        ],
    },
    # ── Cardio ─────────────────────────────────────────────────────────────────
    {
        "name": "Treadmill Run",
        "category": "cardio",
        "muscle_groups": ["quadriceps", "hamstrings", "calves", "glutes"],
        "equipment_needed": ["treadmill"],
        "difficulty": "beginner",
        "instructions": [
            "Set a comfortable pace and warm up for 5 minutes.",
            "Maintain steady running form with upright posture.",
            "Cool down by walking for several minutes.",
        ],
        "tips": "Keep a consistent cadence and land mid-foot to reduce impact.",
    },
    {
        "name": "Stationary Bike",
        "category": "cardio",
        "muscle_groups": ["quadriceps", "hamstrings", "calves"],
        "equipment_needed": ["stationary bike"],
        "difficulty": "beginner",
        "instructions": [
            "Adjust the seat so your leg is slightly bent at the bottom.",
            "Pedal at a steady resistance.",
            "Maintain an upright posture.",
        ],
    },
    {
        "name": "Rowing Machine",
        "category": "cardio",
        "muscle_groups": ["back", "legs", "core", "arms"],
        "equipment_needed": ["rowing machine"],
        "difficulty": "intermediate",
        "instructions": [
            "Push through the legs first, then lean back and pull.",
            "Return in reverse order: arms, body, then legs.",
            "Maintain a smooth rhythm.",
        ],
    },
    {
        "name": "Elliptical",
        "category": "cardio",
        "muscle_groups": ["quadriceps", "hamstrings", "glutes"],
        "equipment_needed": ["elliptical machine"],
        "difficulty": "beginner",
        "instructions": [
            "Stand upright and grip the handles.",
            "Move in a smooth elliptical stride.",
            "Adjust resistance and incline for intensity.",
        ],
    },
    {
        "name": "Jump Rope",
        "category": "cardio",
        "muscle_groups": ["calves", "shoulders", "core"],
        "equipment_needed": ["jump rope"],
        "difficulty": "intermediate",
        "instructions": [
            "Hold the rope with elbows close to your body.",
            "Jump on the balls of your feet, rotating the rope.",
            "Keep a consistent cadence and light landing.",
        ],
    },
    {
        "name": "High-Intensity Interval Training",
        "category": "cardio",
        "muscle_groups": ["legs", "core", "glutes"],
        "equipment_needed": [],
        "difficulty": "advanced",
        "instructions": [
            "Warm up for several minutes.",
            "Perform max-effort bursts (e.g. sprints) followed by active recovery.",
            "Repeat for the prescribed number of rounds.",
        ],
        "contraindications": "Consult a physician before starting if you have a heart condition.",
    },
    {
        "name": "Stair Climber",
        "category": "cardio",
        "muscle_groups": ["quadriceps", "glutes", "calves"],
        "equipment_needed": ["stair climber"],
        "difficulty": "intermediate",
        "instructions": [
            "Stand upright on the machine.",
            "Step continuously at a steady pace.",
            "Avoid leaning heavily on the rails.",
        ],
    },
    {
        "name": "Burpees",
        "category": "cardio",
        "muscle_groups": ["chest", "legs", "core", "shoulders"],
        "equipment_needed": [],
        "difficulty": "advanced",
        "instructions": [
            "From standing, squat down and place hands on the floor.",
            "Kick the feet back into a plank.",
            "Return the feet and jump into the air.",
        ],
    },
    {
        "name": "High Knees",
        "category": "cardio",
        "muscle_groups": ["quadriceps", "hip_flexors", "core"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Run in place, driving knees up to hip height.",
            "Pump your arms opposite to your legs.",
            "Keep a quick cadence.",
        ],
    },
    {
        "name": "Mountain Climbers",
        "category": "cardio",
        "muscle_groups": ["core", "shoulders", "legs"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Start in a high plank position.",
            "Alternate driving your knees toward your chest quickly.",
            "Keep your hips down and core braced.",
        ],
    },
    {
        "name": "Jumping Jacks",
        "category": "cardio",
        "muscle_groups": ["legs", "shoulders", "core"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Stand with feet together and arms at your sides.",
            "Jump while raising arms overhead and spreading feet.",
            "Jump back to the start and repeat.",
        ],
    },
    {
        "name": "Boxing Bag Workout",
        "category": "cardio",
        "muscle_groups": ["shoulders", "arms", "core", "legs"],
        "equipment_needed": ["punching bag", "boxing gloves"],
        "difficulty": "intermediate",
        "instructions": [
            "Assume a boxing stance.",
            "Throw jab, cross, and hook combinations.",
            "Move around the bag and maintain footwork.",
        ],
    },
    # ── Flexibility ────────────────────────────────────────────────────────────
    {
        "name": "Hamstring Stretch",
        "category": "flexibility",
        "muscle_groups": ["hamstrings"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Extend one leg forward with the heel on the floor.",
            "Hinge at the hips to lean toward the extended leg.",
            "Hold for the prescribed time.",
        ],
    },
    {
        "name": "Quadriceps Stretch",
        "category": "flexibility",
        "muscle_groups": ["quadriceps"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Stand and pull one heel toward your glutes.",
            "Keep knees together and hips forward.",
            "Hold for the prescribed time.",
        ],
    },
    {
        "name": "Chest Opener Stretch",
        "category": "flexibility",
        "muscle_groups": ["chest", "shoulders"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Stand tall and interlace your hands behind your back.",
            "Straighten your arms and lift them slightly.",
            "Open the chest and hold.",
        ],
    },
    {
        "name": "Standing Hamstring Bend",
        "category": "flexibility",
        "muscle_groups": ["hamstrings", "lower_back"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Stand with feet hip-width apart.",
            "Hinge at the hips to reach toward your toes.",
            "Keep a slight bend in the knees.",
        ],
    },
    {
        "name": "Hip Flexor Stretch",
        "category": "flexibility",
        "muscle_groups": ["hip_flexors", "quadriceps"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Kneel on one knee with the other foot forward.",
            "Shift your hips forward until you feel a stretch.",
            "Hold and switch sides.",
        ],
    },
    {
        "name": "Triceps Stretch",
        "category": "flexibility",
        "muscle_groups": ["triceps"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Raise one arm overhead and bend the elbow.",
            "Reach the other hand to gently push the elbow down.",
            "Hold and switch sides.",
        ],
    },
    {
        "name": "Shoulder Stretch",
        "category": "flexibility",
        "muscle_groups": ["shoulders"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Bring one arm across your chest.",
            "Use the other hand to gently pull the arm closer.",
            "Hold and switch sides.",
        ],
    },
    # ── Mobility ───────────────────────────────────────────────────────────────
    {
        "name": "World's Greatest Stretch",
        "category": "mobility",
        "muscle_groups": ["hips", "shoulders", "spine", "hamstrings"],
        "equipment_needed": [],
        "difficulty": "intermediate",
        "instructions": [
            "Step forward into a deep lunge.",
            "Place the same-side elbow to the floor inside the front foot.",
            "Rotate the torso to open the chest and raise the arm.",
        ],
    },
    {
        "name": "Cat-Cow Stretch",
        "category": "mobility",
        "muscle_groups": ["spine", "core"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Start on all fours.",
            "Inhale to drop the belly and lift the chest (cow).",
            "Exhale to round the back and tuck the chin (cat).",
        ],
    },
    {
        "name": "Hip Circle",
        "category": "mobility",
        "muscle_groups": ["hips", "glutes"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Stand with hands on your hips.",
            "Trace circles with your hips in one direction.",
            "Repeat in the opposite direction.",
        ],
    },
    {
        "name": "Ankle Rotations",
        "category": "mobility",
        "muscle_groups": ["ankles", "calves"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Lift one foot off the ground.",
            "Rotate the ankle in full circles.",
            "Repeat in the opposite direction and switch feet.",
        ],
    },
    {
        "name": "Deep Squat Hold",
        "category": "mobility",
        "muscle_groups": ["hips", "ankles", "quadriceps"],
        "equipment_needed": [],
        "difficulty": "intermediate",
        "instructions": [
            "Squat down as low as possible keeping heels flat.",
            "Hold a deep position for the prescribed time.",
            "Keep the torso tall and chest up.",
        ],
    },
    {
        "name": "Leg Swings",
        "category": "mobility",
        "muscle_groups": ["hamstrings", "hip_flexors"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Hold onto a stable surface.",
            "Swing one leg forward and backward.",
            "Repeat side-to-side, then switch legs.",
        ],
    },
    {
        "name": "Spinal Twist",
        "category": "mobility",
        "muscle_groups": ["spine", "obliques"],
        "equipment_needed": [],
        "difficulty": "beginner",
        "instructions": [
            "Lie on your back with knees bent to one side.",
            "Rotate the torso gently to the opposite side.",
            "Hold and switch directions.",
        ],
    },
    {
        "name": "Shoulder Dislocates",
        "category": "mobility",
        "muscle_groups": ["shoulders", "chest"],
        "equipment_needed": ["resistance band", "broomstick"],
        "difficulty": "intermediate",
        "instructions": [
            "Hold the band wide in front of you.",
            "Raise it overhead and behind your body.",
            "Keep arms straight and move within your range.",
        ],
        "contraindications": "Go only within a comfortable range to avoid shoulder strain.",
    },
]


class Command(BaseCommand):
    """Seed the exercise library."""

    help = "Populate the exercise library with common exercises."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Tenant ID to seed exercises for. Defaults to the first tenant.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing exercises and categories for the target tenant before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):  # noqa: ARG002
        """Run the seed command."""
        tenant_id = options.get("tenant")
        if tenant_id is None:
            tenant = Tenant.objects.order_by("id").first()
            if tenant is None:
                raise CommandError("No tenant found. Create a tenant first.")
        else:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist as exc:
                raise CommandError(f"Tenant with id {tenant_id} does not exist.") from exc

        if options.get("reset"):
            Exercise.objects.filter(tenant=tenant).delete()
            ExerciseCategory.objects.filter(tenant=tenant).delete()

        categories = self._get_categories(tenant)

        created = 0
        for item in _EXERCISE_DATA:
            category = categories[item["category"]]
            _, was_created = Exercise.objects.get_or_create(
                tenant=tenant,
                name=item["name"],
                defaults={
                    "description": item.get("description", ""),
                    "category": category,
                    "muscle_groups": item["muscle_groups"],
                    "equipment_needed": item.get("equipment_needed", []),
                    "difficulty": item["difficulty"],
                    "instructions": item.get("instructions", []),
                    "media_url": item.get("media_url"),
                    "tips": item.get("tips", ""),
                    "contraindications": item.get("contraindications", ""),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} exercises for tenant '{tenant.name}' "
                f"across {len(categories)} categories.",
            )
        )

    def _get_categories(self, tenant: Tenant) -> dict:
        """Return a mapping of slug to category, creating defaults if absent."""
        defaults = {
            "strength": {
                "name": "Strength",
                "description": "Resistance training to build muscular strength.",
            },
            "cardio": {
                "name": "Cardio",
                "description": "Exercises that raise heart rate and improve endurance.",
            },
            "flexibility": {
                "name": "Flexibility",
                "description": "Stretching to improve range of motion.",
            },
            "mobility": {
                "name": "Mobility",
                "description": "Movement quality and joint control.",
            },
        }
        result = {}
        for slug, data in defaults.items():
            category, _ = ExerciseCategory.objects.get_or_create(
                tenant=tenant,
                slug=slug,
                defaults=data,
            )
            result[slug] = category
        return result
