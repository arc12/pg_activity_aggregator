from pg_shared import LangstringsBase, AnalyticsCore

# Some central stuff which is used by both plain Flask and Dash views.
# This is basically the same as the plaything formula but "analytics things" differ in not having the concept of a specification.
# The language requirement now becomes a query string parameter and selecting the correct "about" markdown relies on it being named like: about_en.md

AT_NAME = "agg-view"

class Langstrings(LangstringsBase):
    langstrings = {
        "MENU_BASIC": {
            "en": "Basic"
        },
        "MENU_ABOUT": {
            "en": "About"
        },
        "BASIC_TITLE": {
            "en": "Basic Aggregated Counts"
        },
        "PLAYTHING_NAME": {
            "en": "Plaything:"
        },
        "SHOW_FACET": {
            "en": "Show Facet:"
        },
        "FILTER_BY": {
            "en": "Filter by:"
        }
        
    }

# The menu is only shown if menu=1 in query-string AND only for specific views. Generally make the menu contain all views it is coded for
# Structure is view: LANGSTRING_KEY,
# - where "view" is the part after the optional plaything_root (and before <specification_id> if present) in the URL. e.g. "about" is a view.
# - and LANGSTRING_KEY is defined in the Langstrings class above
# The ROOT for a plaything is the index cards page and should not be in the menu.
# This defines the default order and the maximum scope of views in the meny. A plaything specification may override.
menu = {
    "about": "MENU_ABOUT",
    "basic": "MENU_BASIC"
}

# This sets up core features such as logger, activity recording, core-config.
core = AnalyticsCore(AT_NAME)