from datetime import date, datetime, time

# Single source of truth for sale.auction: (param_name, type, domain_info).
# Types: "search", "ids", "strings", "date". domain_info: "search" for OR ilike,
# or (field, op). Dates are converted to datetime in the mixin.
AUCTION_FILTER_SPEC = [
    ("search", "search", "search"),
    ("sale_type_ids", "ids", ("sale_type", "in")),
    ("statuses", "strings", ("state", "in")),
    ("date_from", "date", ("sale_date_begin", ">=")),
    ("date_to", "date", ("sale_date_begin", "<=")),
]

# Fields used when domain_info is "search" (OR ilike on sale.auction)
AUCTION_SEARCH_FIELDS = [
    "name",
    "location",
]


class AuctionsFiltersMixin:
    def _apply_filters_to_domain(self, domain, filters):
        if not filters:
            return domain

        spec_map = {entry[0]: entry[2] for entry in AUCTION_FILTER_SPEC if len(entry) >= 3}

        for param_name, value in filters.items():
            domain_info = spec_map.get(param_name)
            if domain_info is None:
                continue

            if domain_info == "search":
                search_domain = ["|"] * (len(AUCTION_SEARCH_FIELDS) - 1) + [
                    (f, "ilike", value) for f in AUCTION_SEARCH_FIELDS
                ]
                domain.extend(search_domain)
                continue

            if isinstance(domain_info, (list, tuple)) and len(domain_info) == 2:
                field, op = domain_info
                if op in (">=", "<=") and isinstance(value, date) and not isinstance(value, datetime):
                    value = datetime.combine(value, time.min if op == ">=" else time.max)
                domain.append((field, op, value))

        return domain
