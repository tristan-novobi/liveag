from datetime import date, datetime, time

# Single source of truth: (param_name, type, domain_info).
# Types: "search", "ids", "strings", "date". domain_info: "search" for OR ilike,
# or (field, op) e.g. ("auction_id", "in"). Dates are converted to datetime in the mixin.
CONTRACT_FILTER_SPEC = [
    ("search", "search", "search"),
    ("auction_id", "ids", ("auction_id", "in")),
    ("statuses", "strings", ("state", "in")),
    ("sale_type", "ids", ("sale_type", "in")),
    ("date_from", "date", ("create_date", ">=")),
    ("date_to", "date", ("create_date", "<=")),
    ("kind_ids", "ids", "kind_or"),  # Special case: OR condition for kind1 OR kind2
]

# Fields used when domain_info is "search" (OR ilike)
CONTRACT_SEARCH_FIELDS = [
    "id",
    "seller_id.name",
    "kind1.name",
    "kind2.name",
    "lot_number",
    "auction_id.name",
]


class ContractsFiltersMixin:
    def _apply_filters_to_domain(self, domain, filters):
        if not filters:
            return domain

        spec_map = {entry[0]: entry[2] for entry in CONTRACT_FILTER_SPEC if len(entry) >= 3}

        for param_name, value in filters.items():
            domain_info = spec_map.get(param_name)
            if domain_info is None:
                continue

            if domain_info == "search":
                search_domain = ["|"] * (len(CONTRACT_SEARCH_FIELDS) - 1) + [
                    (f, "ilike", value) for f in CONTRACT_SEARCH_FIELDS
                ]
                domain.extend(search_domain)
                continue

            # Special case: kind_ids needs OR condition for kind1 OR kind2
            if domain_info == "kind_or":
                if value:  # Only add if there are IDs to filter
                    domain.append("|")
                    domain.append(("kind1", "in", value))
                    domain.append(("kind2", "in", value))
                continue

            if isinstance(domain_info, (list, tuple)) and len(domain_info) == 2:
                field, op = domain_info
                if op in (">=", "<=") and isinstance(value, date) and not isinstance(value, datetime):
                    value = datetime.combine(value, time.min if op == ">=" else time.max)
                domain.append((field, op, value))

        return domain
