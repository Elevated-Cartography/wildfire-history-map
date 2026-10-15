import inspect
import sys
from enum import Enum


class ReasonCode(Enum):
    # Original calfire reasons
    LIGHTNING = (1, "Lightning")
    EQUIPMENT_USE = (2, "Equipment Use")
    SMOKING = (3, "Smoking")
    CAMPFIRE = (4, "Campfire")
    DEBRIS = (5, "Debris")
    RAILROAD = (6, "Railroad")
    ARSON = (7, "Arson")
    PLAYING_WITH_FIRE = (8, "Playing with fire")
    MISCELLANEOUS = (9, "Miscellaneous")
    VEHICLE = (10, "Vehicle")
    POWERLINE = (11, "Powerline")
    FIREFIGHTER_TRAINING = (12, "Firefighter Training")
    NON_FIREFIGHTER_TRAINING = (13, "Non-Firefighter Training")
    UNNOWN_UNIDENTIFIED = (14, "Unknown/Unidentified")
    STRUCTURE = (15, "Structure")
    AIRCRAFT = (16, "Aircraft")
    VOLCANIC = (17, "Volcanic")
    ESCAPED_PRESRIBED_BURN = (18, "Escaped Prescribed Burn")
    ILLEGAL_ALIEN_CAMPFIRE = (19, "Illegal Alien Campfire")

    # Extra Reasons from NIFC
    FIREWORKS = (20, "Fireworks")
    AGRICULTURAL = (21, "Agricultural")
    COAL_SEAM = (22, "Coal Seam")
    FIREARMS = (23, "Firearms")
    DRUG_OPERATIONS = (24, "Drug Operations")
    ELECTRIC_FENCE = (25, "Electric Fence")
    UTILITIES = (26, "Utilities")

    # Sources that only say a fire was human caused, not how (NBAC)
    HUMAN_UNSPECIFIED = (27, "Human (unspecified)")

    def __init__(self, num, nice_str):
        self.num = num
        self.nice_str = nice_str


class NIFCRulesEngine:
    def __init__(self):
        self.unmatched = set()
        self.multiple_matches = set()
        self.rules = []
        self._load_rules()

    def _load_rules(self):
        self.rules = [
            obj
            for name, obj in inspect.getmembers(sys.modules[__name__])
            if (inspect.isfunction(obj) and name.startswith("_rule"))
        ]

    def match(self, cause, general, specific):
        # The rules expect empty strings, but the APIs return nulls
        cause, general, specific = (v or "" for v in (cause, general, specific))
        reasons = []
        for rule in self.rules:
            reason = rule(cause, general, specific)
            if reason:
                reasons.append(reason)
        if len(reasons) == 0:
            self.unmatched.add((cause, general, specific))

        if len(reasons) > 1:
            # Don't fail the whole build over this, `surtr reason-test` lists them
            self.multiple_matches.add((cause, general, specific, tuple(reasons)))
        if reasons:
            return reasons[0]
        else:
            return None


def _rule_no_cause(cause, general, specific):
    if not cause:
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif cause in ["Human", "Unknown", "Undetermined"] and not general and not specific:
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif cause == "Human" and general.startswith("Undetermined"):
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif cause == "Natural" and general == "Undetermined":
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif (cause, general, specific) == (
        "Human",
        "Cause and Origin Not Identified",
        "Other, Unknown",
    ):
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif (cause, general, specific) == ("Human", "Cause and Origin Not Identified", ""):
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif general == "Investigated but Undetermined" and specific == "":
        return ReasonCode.UNNOWN_UNIDENTIFIED
    elif (cause, general, specific) in [
        ("Natural", "Cause and Origin Not Identified", ""),
        ("Unknown", "Cause and Origin Not Identified", ""),
        ("Undetermined", "Undetermined", ""),
        ("Undetermined", "Undetermined (remarks required)", ""),
        ("Human", "Incendiary", "Not investigated"),
        ("Undetermined", "Undetermined", "Not investigated"),
        ("Undetermined", "Undetermined (remarks required)", "Not investigated"),
        ("Human", "Utilities", "Not investigated"),
        ("Human", "Other Human Cause", "Origin and/or cause not identified"),
        ("Undetermined", "Other Human Cause", "Origin and/or cause not identified"),
        ("Undetermined", "Undetermined", "Origin and/or cause not identified"),
        (
            "Undetermined",
            "Undetermined (remarks required)",
            "Origin and/or cause not identified",
        ),
        ("Human", "Debris/Open Burning", "Origin destroyed"),
        ("Human", "Other Human Cause", "Origin destroyed"),
        ("Undetermined", "Undetermined", "Origin destroyed"),
        ("Undetermined", "Undetermined (remarks required)", "Origin destroyed"),
        ("Human", "Other causes", "Unknown (remarks required)"),
        ("Unknown", "Cause and Origin Not Identified", "Other, Unknown"),
        ("Human", "Incendiary", "Other, Unknown"),
        ("Human", "Investigated but Undetermined", "Other, Unknown"),
        ("Unknown", "Investigated but Undetermined", "Other, Unknown"),
        ("Human", "Other Human Cause", "Other, Unknown"),
        ("Undetermined", "Other Human Cause", "Other, Unknown"),
        ("Unknown", "Other Human Cause", "Other, Unknown"),
        ("Natural", "Other Natural Cause", "Other, Unknown"),
        ("Undetermined", "Undetermined", "Other, Unknown"),
        ("Undetermined", "Undetermined", "Under investigation"),
        ("Undetermined", "Undetermined (remarks required)", "Under investigation"),
        ('Human', 'Other Human Cause', 'Under investigation'),
        ('Human', 'Incendiary', 'Origin and/or cause not identified')
    ]:
        return ReasonCode.UNNOWN_UNIDENTIFIED


def _rule_arson(cause, general, specific):
    if specific and specific.startswith("Arson"):
        return ReasonCode.ARSON
    elif cause == "Human" and general == "Arson":
        return ReasonCode.ARSON


def _rule_campfire(cause, general, specific):
    if (
        specific
        in [
            "Campfire",
            "Bonfire",
            "Cooking Fire",
            "Bonfire/party fire",
            "Outdoor oven/fireplace/metal fire ring",
        ]
        and general != "Lightning"
    ):
        return ReasonCode.CAMPFIRE


def _rule_aircraft(cause, general, specific):
    if specific == "Aircraft":
        return ReasonCode.AIRCRAFT


def _rule_railroad(cause, general, specific):
    if general == "Railroad" and not specific:
        return ReasonCode.RAILROAD
    elif specific == "Rail/Track Grinding":
        return ReasonCode.RAILROAD
    elif (
        general == "Railroad"
        and not specific.startswith("Fireworks")
        and not specific.startswith("Cutting/Welding")
    ):
        return ReasonCode.RAILROAD
    elif general == "Railroad operations and maintenance":
        return ReasonCode.RAILROAD
    elif (cause, general, specific) == (
        "Unknown",
        "Other Human Cause",
        "Accident/Derailment",
    ):
        return ReasonCode.RAILROAD
    elif (cause, general, specific) in [
        ("Unknown", "Cause and Origin Not Identified", "Accident/Derailment"),
        ("Human", "Debris/Open Burning", "Accident/Derailment"),
        ("Human", "Equipment", "Accident/Derailment"),
        ("Human", "Other Human Cause", "Accident/Derailment"),
        ("Human", "Utilities", "Accident/Derailment"),
    ]:
        return ReasonCode.RAILROAD


def _rule_smoking(cause, general, specific):
    if cause == "Unknown" and general == "Smoking":
        return ReasonCode.SMOKING
    elif cause == "Human" and general == "Smoking":
        return ReasonCode.SMOKING
    elif specific in ["Cigar", "Cigarette", "Smoking"]:
        return ReasonCode.SMOKING
    elif (cause, general, specific) in [
        ("Human", "Other Human Cause", "Pipe"),
        ("Undetermined", "Smoking", "Other, Unknown"),
        ("Natural", "Smoking", ""),
        ("Undetermined", "Smoking", ""),
    ]:
        return ReasonCode.SMOKING


def _rule_prescribed_burn(cause, general, specific):
    if (
        general == "Human"
        and general == "Debris and open burning"
        and specific == "Escaped Prescribed Burn"
    ):
        return ReasonCode.ESCAPED_PRESRIBED_BURN
    elif (cause, general, specific) == (
        "Undetermined",
        "Debris/Open Burning",
        "Broadcast/Prescribed Burn",
    ):
        return ReasonCode.ESCAPED_PRESRIBED_BURN
    elif specific == "Broadcast/Prescribed Burn":
        return ReasonCode.ESCAPED_PRESRIBED_BURN


def _rule_fireworks(cause, general, specific):
    if cause == "Human" and general == "Fireworks":
        return ReasonCode.FIREWORKS
    elif specific == "Fireworks (Consumer or Personal Use)":
        return ReasonCode.FIREWORKS
    elif specific == "Fireworks (Display or Professional Use)":
        return ReasonCode.FIREWORKS


def _rule_lighning(cause, general, specific):
    if cause == "Unknown" and general == "Lightning":
        return ReasonCode.LIGHTNING
    elif cause == "Natural" and general == "Lightning":
        return ReasonCode.LIGHTNING
    elif (cause, general, specific) == ("Natural", "Natural", "Lightning"):
        return ReasonCode.LIGHTNING
    elif (cause, general, specific) in [
        ("Human", "Lightning", ""),
        ("Undetermined", "Lightning", ""),
    ]:
        return ReasonCode.LIGHTNING


def _rule_powerline(cause, general, specific):
    if specific == "Power Generation/Transmission" and general != "Lightning":
        return ReasonCode.POWERLINE
    elif (cause, general, specific) == ("Human", "Utilities", "Dynamic Grid Failure"):
        return ReasonCode.POWERLINE
    elif (cause, general, specific) in [
        (
            "Human",
            "Power generation/transmission/distribution",
            "Electrical transmission/distribution systems",
        ),
    ]:
        return ReasonCode.POWERLINE


def _rule_structure(cause, general, specific):
    if specific == "Structure" and general != "Smoking":
        return ReasonCode.STRUCTURE


def _rule_playing_with_fire(cause, general, specific):
    if specific == "Fire Play":
        return ReasonCode.PLAYING_WITH_FIRE
    elif general == "Misuse of fire by a minor":
        return ReasonCode.PLAYING_WITH_FIRE
    elif specific == "Glass Refraction/Magnification":
        return ReasonCode.PLAYING_WITH_FIRE


def _rule_agricultural(cause, general, specific):
    if specific == "Farming Equipment" or specific == "Agricultural":
        return ReasonCode.AGRICULTURAL


def _rule_firearms(cause, general, specific):
    if specific in [
        "Ammunition",
        "Exploding Targets",
        "Exploding target shooting",
        "Inert target shooting",
        "Incendiary Ammunition",
        "Armor Piercing Incendiary/Tracer Ammunition",
        "Steel Component Ammunition",
    ]:
        return ReasonCode.FIREARMS
    elif (
        general == "Firearms/Weapons"
        and not specific.startswith("Fireworks")
        and not specific.startswith("Bonfire")
    ):
        return ReasonCode.FIREARMS
    elif (
        general == "Firearms and explosives use"
        and specific == "Unspecified shooting (for historical mapping only)"
    ):
        return ReasonCode.FIREARMS
    elif general == "Incendiary" and specific == "Incendiary Tracer Ammunition":
        return ReasonCode.FIREARMS
    elif (cause, general, specific) in [
        ("Human", "Firearms and explosives use", "Other (remarks required)"),
        ("Human", "Firearms and explosives use", "Unknown (remarks required)"),
        ("Human", "Firearms and explosives use", ""),
        ('Human', 'Firearms and explosives use', 'Flares/fuses'),
    ]:
        return ReasonCode.FIREARMS


def _rule_coal_seam(cause, general, specific):
    if general == "Coal Seam":
        return ReasonCode.COAL_SEAM


def _rule_equipment_use(cause, general, specific):
    if specific in [
        "Catalyst Welding",
        "Chainsaw/brush saw/weed trimmer",
        "Cutting/Welding",
        "Electric motor/power tools/battery",
        "Heavy Equipment",
        "Heavy equipment & implements",
        "Logging Equipment",
        "Power Tools",
        "Small Engine Equipment",
        "Tractors/mowers/brush hogs",
        "Hot work: welder/grinder/torch/cutter",
    ]:
        return ReasonCode.EQUIPMENT_USE
    elif general == "Equipment" and specific in [
        "",
        "Mowing",
        "Exhaust System Particle",
        "Right-of-Way Maintenance",
        "Wheel Bearing Failure",
    ]:
        return ReasonCode.EQUIPMENT_USE
    elif general == "Equipment and vehicle use" and specific in [
        "Other (remarks required)",
        "Other small engine equipment",
        "Trailer",
        "Unknown (remarks required)",
    ]:
        return ReasonCode.EQUIPMENT_USE
    elif (cause, general, specific) in [
        ("Human", "Equipment", "Other, Known"),
        ("Undetermined", "Equipment", "Other, Known"),
        ("Human", "Equipment and vehicle use", ""),
        ("Human", "Equipment", "Blasting"),
        ("Human", "Equipment", "Cooking"),
        ("Human", "Equipment", "Ditch/Fence"),
        ("Human", "Equipment", "Flares"),
        ("Human", "Equipment", "Land Clearing"),
        ("Human", "Equipment", "Oil and Gas Production"),
        ("Human", "Equipment", "Other, Unknown"),
        ("Human", "Equipment", "Spontaneous Combustion"),
        ("Human", "Equipment", "Wheel Slip/Slide"),
        ('Natural', 'Other Natural Cause', 'Mowing'),
    ]:
        return ReasonCode.EQUIPMENT_USE


def _rule_vehicle(cause, general, specific):
    if specific in ["Motor Vehicle", "Motor Vehicles"] and general != "Lightning":
        return ReasonCode.VEHICLE
    elif (cause, general, specific) == ('Human', 'Camping', 'Motor Vehicle'):
        return ReasonCode.VEHICLE
    elif general == "Equipment and vehicle use" and specific in [
        "Commercial transport vehicle",
        "OHV/ATV/motorcycle",
        "Passenger vehicle/motorized RV",
    ]:
        return ReasonCode.VEHICLE
    elif (cause, general, specific) == (
        "Undetermined",
        "Undetermined",
        "Motor Vehicle",
    ):
        return ReasonCode.VEHICLE
    elif (
        cause == "Human"
        and general == "Equipment"
        and specific.startswith("Motor Vehicle")
    ):
        return ReasonCode.VEHICLE
    elif (
        cause == "Unknown"
        and general == "Equipment"
        and specific.startswith("Motor Vehicle")
    ):
        return ReasonCode.VEHICLE
    elif (
        cause == "Unknown"
        and general == "Investigated but Undetermined"
        and specific.startswith("Motor Vehicle")
    ):
        return ReasonCode.VEHICLE
    elif (
        cause == "Unknown"
        and general == "Other Human Cause"
        and specific.startswith("Motor Vehicle")
    ):
        return ReasonCode.VEHICLE
    elif (
        cause == "Unknown"
        and general == "Cause and Origin Not Identified"
        and specific.startswith("Motor Vehicle")
    ):
        return ReasonCode.VEHICLE
    elif (cause, general, specific) in [
        ("Human", "Debris/Open Burning", "Motor Vehicle"),
        ("Undetermined", "Equipment", "Motor Vehicle"),
        ("Human", "Incendiary", "Motor Vehicle"),
        ("Human", "Other Human Cause", "Motor Vehicle"),
        ("Human", "Utilities", "Motor Vehicle"),
        ("Undetermined", "Equipment", "Motor Vehicles"),
        ("Human", "Other Human Cause", "Motor Vehicles"),
        ("Human", "Cause and Origin Not Identified", "Brake Shoe Particle"),
        ("Human", "Equipment", "Brake Shoe Particle"),
        ("Human", "Other Human Cause", "Brake Shoe Particle"),
        ("Unknown", "Other Human Cause", "Brake Shoe Particle"),
        ('Human', 'Incendiary', 'Exhaust System Particle'),
        ('Human', 'Other Human Cause', 'Exhaust System Particle'),
        ('Unknown', 'Other Human Cause', 'Exhaust System Particle'),
        ('Human', 'Other Human Cause', 'Wheel Bearing Failure'),
    ]:
        return ReasonCode.VEHICLE


def _rule_electric_fence(cause, general, specific):
    if specific == "Electric Fence" or specific == "Electric Fences":
        return ReasonCode.ELECTRIC_FENCE
    elif (cause, general, specific) == ("Human", "Other causes", "Electric fence"):
        return ReasonCode.ELECTRIC_FENCE


def _rule_drug_operations(cause, general, specific):
    if specific == "Drug Operations":
        return ReasonCode.DRUG_OPERATIONS


def _rule_debris(cause, general, specific):
    if specific == "Yard Debris" or specific == "Yard debris":
        return ReasonCode.DEBRIS
    if cause == "Human" and "general" == "Debris and open burning":
        return ReasonCode.DEBRIS
    if (
        cause == "Unknown"
        and general == "Debris/Open Burning"
        and specific != "Agricultural"
    ):
        return ReasonCode.DEBRIS
    elif (
        general
        in [
            "Debris Burning (Fire Use)",
            "Debris and open burning",
            "Debris/Open Burning",
        ]
        and specific == ""
    ):
        return ReasonCode.DEBRIS
    elif (cause, general, specific) in [
        ("Human", "Debris/Open Burning", "Other, Unknown"),
        ("Human", "Debris/Open Burning", "Other, Known"),
        ("Undetermined", "Debris/Open Burning", "Other, Known"),
        ("Human", "Debris/Open Burning", "Other, Unknown"),
        ("Human", "Debris and open burning", "Other (remarks required)"),
        ("Human", "Debris and open burning", "Branding"),
        ("Human", "Debris and open burning", "Burn Barrel"),
        ("Human", "Debris and open burning", "Burning personal items"),
        ("Human", "Debris and open burning", "Distress/signal fire"),
        ("Human", "Debris and open burning", "Ditch/fence line burning"),
        ("Human", "Debris and open burning", "Escaped Prescribed Burn"),
        ("Human", "Debris and open burning", "Field/agricultural burn"),
        ("Human", "Debris and open burning", "Hand pile/slash"),
        ("Human", "Debris and open burning", "Machine pile/slash"),
        ("Human", "Debris and open burning", "Open trash burning"),
        ("Human", "Debris and open burning", "Other land clearing"),
        ("Human", "Debris and open burning", "Pest control/deterrent/smoke out"),
        ("Human", "Debris and open burning", "Right-of-way clearing"),
        ("Human", "Debris and open burning", "Unknown (remarks required)"),
        ("Human", "Debris/Open Burning", "Ash Disposal"),
        ("Human", "Debris/Open Burning", "Barrel"),
        ("Human", "Debris/Open Burning", "Blasting"),
        ("Human", "Debris/Open Burning", "Ceremonial/Cultural"),
        ("Human", "Debris/Open Burning", "Cooking"),
        ("Human", "Debris/Open Burning", "Cultural"),
        ("Human", "Debris/Open Burning", "Ditch/Fence"),
        ("Human", "Debris/Open Burning", "Dump Burning"),
        ("Human", "Debris/Open Burning", "Field Burning"),
        ("Human", "Debris/Open Burning", "Flue Sparks"),
        ("Human", "Debris/Open Burning", "Grazing Improvement"),
        ("Human", "Debris/Open Burning", "Habitat Improvement"),
        ("Human", "Debris/Open Burning", "Home Outdoor Wood Burning Furnaces"),
        ("Human", "Debris/Open Burning", "Land Clearing"),
        ("Human", "Debris/Open Burning", "Lighter"),
        ("Human", "Debris/Open Burning", "Match(s)"),
        ("Human", "Debris/Open Burning", "Oil and Gas Production"),
        ("Human", "Debris/Open Burning", "Right-of-Way"),
        ("Human", "Debris/Open Burning", "Right-of-Way Maintenance"),
        ("Human", "Debris/Open Burning", "Spontaneous Combustion"),
        ("Human", "Debris/Open Burning", "Trash Burning"),
        ("Human", "Debris/Open Burning", "Warming"),
        ("Human", "Other Human Cause", "Trash Burning"),
        ("Human", "Other Human Cause", "Dump Burning"),
        ('Undetermined', 'Debris/Open Burning', 'Ditch/Fence'),
        ('Undetermined', 'Debris/Open Burning', 'Field Burning'),
        ('Undetermined', 'Debris/Open Burning', 'Trash Burning'),
        ('Unknown', 'Investigated but Undetermined', 'Trash Burning'),
        ('Human', 'Other Human Cause', 'Field Burning'),
        ('Unknown', 'Cause and Origin Not Identified', 'Trash Burning'),
        ('Human', 'Incendiary', 'Dump Burning'),
        ('Human', 'Camping', 'Trash Burning'),
        ('Human', 'Incendiary', 'Trash Burning'),
        ('Unknown', 'Cause and Origin Not Identified', 'Barrel'),
        ('Human', 'Incendiary', 'Barrel'),
        ('Unknown', 'Investigated but Undetermined', 'Barrel'),
        ('Human', 'Other Human Cause', 'Barrel'),
        ('Unknown', 'Cause and Origin Not Identified', 'Ash Disposal'),
        ('Human', 'Incendiary', 'Ash Disposal'),
        ('Human', 'Other Human Cause', 'Ash Disposal'),
        ('Undetermined', 'Other Human Cause', 'Ash Disposal'),
        ('Unknown', 'Other Human Cause', 'Ash Disposal'),
        ('Human', 'Camping', 'Dump Burning'),
    ]:
        return ReasonCode.DEBRIS


def _rule_misc(cause, general, specific):
    triplet = (cause, general, specific)
    if triplet == ("Human", "Cause and Origin Not Identified", "Other, Known"):
        return ReasonCode.MISCELLANEOUS
    elif triplet == ("Human", "Misc/Other", ""):
        return ReasonCode.MISCELLANEOUS
    elif triplet == ("Human", "Other Human Cause", "Not investigated"):
        return ReasonCode.MISCELLANEOUS
    elif triplet == ("Human", "Other Human Cause", "Other, Known"):
        return ReasonCode.MISCELLANEOUS
    elif triplet == ("Human", "Other causes", ""):
        return ReasonCode.MISCELLANEOUS
    elif general == "Other Human Cause" and specific == "":
        return ReasonCode.MISCELLANEOUS
    elif (cause, general, specific) in [
        ("Natural", "Misc/Other", ""),
        ("Undetermined", "Misc/Other", ""),
        ("Human", "Natural", ""),
        ("Natural", "Natural", ""),
        ("Undetermined", "Natural", ""),
        ("Human", "Other Natural Cause", ""),
        ("Natural", "Other Natural Cause", ""),
        ("Unknown", "Other Natural Cause", ""),
        ("Human", "Utilities", "Other, Unknown"),
        ("Unknown", "Utilities", "Other, Unknown"),
        ("Human", "", "Other, Known"),
        ("Human", "Camping", "Other, Known"),
        ("Natural", "Cause and Origin Not Identified", "Other, Known"),
        ("Unknown", "Cause and Origin Not Identified", "Other, Known"),
        ("Human", "Incendiary", "Other, Known"),
        ("Undetermined", "Incendiary", "Other, Known"),
        ("Unknown", "Investigated but Undetermined", "Other, Known"),
        ("Undetermined", "Other Human Cause", "Other, Known"),
        ("Natural", "Other Natural Cause", "Other, Known"),
        ("Human", "Utilities", "Other, Unknown"),
        ("Unknown", "Utilities", "Other, Unknown"),
        ("Human", "Utilities", "Other, Known"),
        ("Undetermined", "Utilities", "Other, Known"),
        ("Unknown", "Utilities", "Other, Known"),
        ("Human", "Camping", "Other, Unknown"),
        ("Natural", "", ""),
        ("Human", "Camping", ""),
        ("Natural", "Camping", ""),
        ("Undetermined", "Camping", ""),
        ("Unknown", "Camping", ""),
        ("Human", "Incendiary", ""),
        ("Undetermined", "Incendiary", ""),
        ("Unknown", "Incendiary", ""),
        ("Human", "Camping", "Ash Disposal"),
        ("Human", "Camping", "Ceremonial/Cultural"),
        ("Human", "Camping", "Lantern/Catalytic Heater"),
        ("Human", "Cause and Origin Not Identified", "Incendiary Device"),
        ('Human', 'Other causes', 'Other (remarks required)'),
        ('Human', 'Camping', 'Warming'),
        ('Undetermined', 'Camping', 'Warming'),
        ('Unknown', 'Camping', 'Warming'),
        ('Unknown', 'Cause and Origin Not Identified', 'Warming'),
        ('Unknown', 'Investigated but Undetermined', 'Warming'),
        ('Human', 'Other Human Cause', 'Warming'),
        ('Unknown', 'Other Human Cause', 'Warming'),
        ('Human', 'Recreation and ceremony', ''),
        ('Human', 'Other Human Cause', 'Ceremonial/Cultural'),
        ('Human', 'Incendiary', 'Cultural'),
        ('Human', 'Other Human Cause', 'Cultural'),
        ('Natural', 'Natural', 'Other (remarks required)'),
        ('Human', 'Recreation and ceremony', 'Other (remarks required)'),

        # Not sure about all these, but i'm tired of doing this, lol
        ('Human', 'Recreation and ceremony', 'Barbeque/smoker'),
        ('Human', 'Incendiary', 'Blasting'),
        ('Human', 'Other Human Cause', 'Blasting'),
        ('Human', 'Camping', 'Cooking'),
        ('Undetermined', 'Camping', 'Cooking'),
        ('Human', 'Incendiary', 'Cooking'),
        ('Human', 'Other Human Cause', 'Cooking'),
        ('Unknown', 'Other Human Cause', 'Cooking'),
        ('Unknown', 'Cause and Origin Not Identified', 'Ditch/Fence'),
        ('Human', 'Incendiary', 'Ditch/Fence'),
        ('Unknown', 'Investigated but Undetermined', 'Ditch/Fence'),
        ('Human', 'Other Human Cause', 'Ditch/Fence'),
        ('Human', 'Other Human Cause', 'Drug Paraphernalia'),
        ('Human', 'Incendiary', 'Field Burning'),
        ('Unknown', 'Investigated but Undetermined', 'Field Burning'),
        ('Natural', 'Other Natural Cause', 'Field Burning'),
        ('Human', 'Incendiary', 'Flares'),
        ('Human', 'Other Human Cause', 'Flares'),
        ('Undetermined', 'Other Human Cause', 'Flares'),
        ('Human', 'Other Human Cause', 'Flue Sparks'),
        ('Unknown', 'Other Human Cause', 'Flue Sparks'),
        ('Human', 'Recreation and ceremony', 'Gas cooking/warming/lighting device'),
        ('Human', 'Incendiary', 'Grazing Improvement'),
        ('Human', 'Other Human Cause', 'Grazing Improvement'),
        ('Human', 'Incendiary', 'Habitat Improvement'),
        ('Undetermined', 'Incendiary', 'Habitat Improvement'),
        ('Unknown', 'Investigated but Undetermined', 'Habitat Improvement'),
        ('Human', 'Other Human Cause', 'Home Outdoor Wood Burning Furnaces'),
        ('Human', 'Incendiary', 'Incendiary Device'),
        ('Human', 'Other Human Cause', 'Incendiary Device'),
        ('Human', 'Incendiary', 'Land Clearing'),
        ('Undetermined', 'Incendiary', 'Land Clearing'),
        ('Human', 'Investigated but Undetermined', 'Land Clearing'),
        ('Unknown', 'Investigated but Undetermined', 'Land Clearing'),
        ('Human', 'Other Human Cause', 'Land Clearing'),
        ('Unknown', 'Cause and Origin Not Identified', 'Lighter'),
        ('Human', 'Incendiary', 'Lighter'),
        ('Unknown', 'Investigated but Undetermined', 'Lighter'),
        ('Human', 'Other Human Cause', 'Lighter'),
        ('Undetermined', 'Undetermined', 'Lighter'),
        ('Human', 'Recreation and ceremony', 'Luminary (aerial/ground)'),
        ('Human', 'Incendiary', 'Match(s)'),
        ('Human', 'Other Human Cause', 'Match(s)'),
        ('Human', 'Camping', 'Portable Stove'),
        ('Human', 'Other Human Cause', 'Right-of-Way'),
        ('Human', 'Incendiary', 'Right-of-Way Maintenance'),
        ('Human', 'Other Human Cause', 'Smoke Out'),
        ('Human', 'Camping', 'Smoker/Camp Stove'),
        ('Human', 'Other Human Cause', 'Smoker/Camp Stove'),
        ('Human', 'Other Human Cause', 'Spontaneous Combustion'),
        ('Natural', 'Other Natural Cause', 'Spontaneous Combustion'),
        ('Human', 'Other causes', 'Spontaneous combustion'),
    ]:
        return ReasonCode.MISCELLANEOUS


def _rule_utilities(cause, general, specific):
    if (cause, general, specific) in [
        ("Human", "Utilities", ""),
        ("Natural", "Utilities", ""),
        ("Undetermined", "Utilities", ""),
        ("Unknown", "Utilities", ""),
        ("Human", "Utilities", "Right-of-Way"),
        ("Human", "Utilities", "Flares"),
        ("Human", "Utilities", "Lantern/Catalytic Heater"),
        ("Human", "Utilities", "Oil and Gas Production"),
        ('Human', 'Power generation/transmission/distribution', ''),
        ('Human', 'Power generation/transmission/distribution', 'Oil/gas production/transportation'),
        ('Human', 'Power generation/transmission/distribution', 'Other (remarks required)'),
        ('Human', 'Power generation/transmission/distribution', 'Solar utility system'),
        ('Undetermined', 'Equipment', 'Oil and Gas Production'),
        ('Human', 'Other Human Cause', 'Oil and Gas Production'),
    ]:
        return ReasonCode.UTILITIES


# @staticmethod
# def from_nifc_data(cause, cause_general, cause_specific):
#     # If the fire cause is none, then there is no more info to be had and we
#     # can mark it as unknown
#     if not cause:
#         return ReasonCode.UNNOWN_UNIDENTIFIED

#     if cause == "Unknown":
#         # If both general and specific are none, then return unknown
#         if cause_general == "" and cause_specific == "":
#             return ReasonCode.UNNOWN_UNIDENTIFIED
#         if cause_general == "":
#             if cause_specific == "Campfire":
#                 return ReasonCode.CAMPFIRE
#         if cause_general == "Cause and Origin Not Identified":
#             if cause_specific == "":
#                 return ReasonCode.UNNOWN_UNIDENTIFIED
#             elif cause_specific.startswith("Arson"):
#                 return ReasonCode.ARSON
#             elif cause_specific == "Other, Unknown":
#                 return ReasonCode.UNNOWN_UNIDENTIFIED
#             elif cause_specific == "Rail/Track Grinding":
#                 return ReasonCode.RAILROAD
#             elif cause_specific == "Motor Vehicle":
#                 return ReasonCode.VEHICLE
#             elif cause_specific == "Structure":
