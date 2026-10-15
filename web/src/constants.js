const REASON_CODES = {
    "1": "Lightning",
    "2": "Equipment Use",
    "3": "Smoking",
    "4": "Campfire",
    "5": "Debris",
    "6": "Railroad",
    "7": "Arson",
    "8": "Playing with fire",
    "9": "Miscellaneous",
    "10": "Vehicle",
    "11": "Powerline",
    "12": "Firefighter Training",
    "13": "Non-Firefighter Training",
    "14": "Unknown/Unidentified",
    "15": "Structure",
    "16": "Aircraft",
    "17": "Volcanic",
    "18": "Escaped Prescribed Burn",
    "19": "Illegal Alien Campfire",
    // Extra reasons from NIFC (see ReasonCode in src/surtr/reason.py)
    "20": "Fireworks",
    "21": "Agricultural",
    "22": "Coal Seam",
    "23": "Firearms",
    "24": "Drug Operations",
    "25": "Electric Fence",
    "26": "Utilities",
    "27": "Human (unspecified)",
}

export {
    REASON_CODES
}
// Short names for the `source` property (see sources.toml)
const SOURCE_LABELS = {
    "calfire": "CAL FIRE",
    "nifc-history": "NIFC",
    "wfigs-perimeters": "WFIGS",
    "nbac": "NBAC",
}

export {
    SOURCE_LABELS
}
