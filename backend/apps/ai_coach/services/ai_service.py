"""Mock AI service for FBOS-017."""

from apps.customers.models import Customer
from apps.diet.models import DietAssignment
from apps.workouts.models import WorkoutAssignment


def build_user_context(user):
    """Build context dict from user's fitness data."""
    ctx = {
        "name": user.get_full_name() or user.email,
        "role": user.role,
        "goals": [],
        "workouts": [],
        "diet_plans": [],
    }
    try:
        customer = Customer.objects.filter(user=user).first()
        if customer and customer.fitness_goals:
            ctx["goals"] = customer.fitness_goals
    except Exception:
        pass
    try:
        assignments = WorkoutAssignment.objects.filter(user=user).select_related("plan")[:3]
        ctx["workouts"] = [
            {"name": a.plan.name, "difficulty": a.plan.difficulty} for a in assignments if hasattr(a, "plan")
        ]
    except Exception:
        pass
    try:
        diet_assignments = DietAssignment.objects.filter(user=user).select_related("plan")[:3]
        ctx["diet_plans"] = [{"name": a.plan.name} for a in diet_assignments if hasattr(a, "plan")]
    except Exception:
        pass
    return ctx


def generate_response(message, user, conversation=None):
    """Generate a mock AI response based on user context."""
    ctx = build_user_context(user)
    msg_lower = message.lower()
    if "workout" in msg_lower or "exercise" in msg_lower:
        rec_type = "workout"
        if ctx["workouts"]:
            response = (
                "Based on your current workout plan "
                f"'{ctx['workouts'][0]['name']}', I recommend focusing on "
                "progressive overload. Increase weight by 5% each week."
            )
        else:
            response = (
                "I recommend starting with a 3-day full-body split: squats, bench press, "
                "rows on day 1; deadlifts, overhead press, pull-ups on day 2; lunges, "
                "incline press, cables on day 3."
            )
    elif "diet" in msg_lower or "nutrition" in msg_lower or "food" in msg_lower:
        rec_type = "diet"
        if ctx["diet_plans"]:
            response = (
                "You have an active diet plan "
                f"'{ctx['diet_plans'][0]['name']}'. Make sure to hit your "
                "protein target and drink 3L of water daily."
            )
        else:
            response = (
                "For a balanced diet, aim for 1.6g protein per kg bodyweight, "
                "40% carbs, 30% protein, 30% fat. Include Indian staples like "
                "roti, dal, curd, and vegetables."
            )
    elif "form" in msg_lower or "technique" in msg_lower:
        rec_type = "exercise_tips"
        response = (
            "Key form tips: keep your core braced, control the eccentric "
            "(lowering) phase for 2-3 seconds, and never round your lower back "
            "during lifts."
        )
    else:
        rec_type = "general"
        response = (
            "Hi "
            f"{ctx['name']}! I'm your AI fitness coach. I can help with workout "
            "recommendations, diet advice, and exercise form tips. "
            "What would you like to know?"
        )
    recommendation = (
        {"type": rec_type, "content": {"suggestion": response, "context": ctx}} if rec_type != "general" else None
    )
    return response, recommendation
