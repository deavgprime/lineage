"""What each jurisdiction pack loads from OpenSanctions."""

SANCTIONS_LISTS = {
    "uk": {"UK FCDO Sanctions List"},
    "uae": {
        "United Arab Emirates Local Terrorist List",
        "UN Security Council Consolidated Sanctions",
    },
}
PEP_COUNTRIES = {"uk": "gb", "uae": "ae"}
SCHEMAS = {"Person", "Company", "Organization"}
