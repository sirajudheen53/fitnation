import { Badge } from "@/components/ui/Badge";

interface DeletedUserBadgeProps {
  className?: string;
}

/**
 * Issue #81 marker for a reference to a deleted customer.
 *
 * Render next to the (backend-provided) "Deleted user" display name on rows
 * whose `customer_is_deleted` / `person_is_deleted` flag is set — the name
 * alone is not distinguishable from a member actually named that.
 */
export function DeletedUserBadge({ className = "" }: DeletedUserBadgeProps) {
  return (
    <Badge variant="default" className={className} title="This member was deleted">
      Deleted
    </Badge>
  );
}
