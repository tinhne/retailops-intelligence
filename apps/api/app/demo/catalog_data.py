"""Static reference data for the fictional demo store "Kestrel Home & Kitchen".

All names are invented. Nothing here describes a real business, person or customer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierSpec:
    name: str
    lead_time_days: int


SUPPLIERS: tuple[SupplierSpec, ...] = (
    SupplierSpec("Northfield Ceramics Co.", 21),
    SupplierSpec("Copperline Cookware Ltd.", 28),
    SupplierSpec("Alder & Ash Woodworks", 14),
    SupplierSpec("Bluewater Glassworks", 18),
    SupplierSpec("Harbor Textile Mill", 10),
    SupplierSpec("Summit Kitchen Supply", 7),
    SupplierSpec("Prairie Storage Goods", 12),
    SupplierSpec("Lantern Coffee Equipment", 25),
)


@dataclass(frozen=True)
class CategorySpec:
    code: str
    name: str
    supplier_index: int
    price_range: tuple[int, int]  # whole dollars
    items: tuple[str, ...]
    variants: tuple[str, ...]


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        "CW",
        "Cookware",
        1,
        (34, 189),
        ("Saucepan 2 qt", "Saute Pan 10 in", "Dutch Oven 5.5 qt", "Skillet 12 in", "Stockpot 8 qt"),
        ("Copper Core", "Enameled Cast Iron", "Tri-Ply Steel"),
    ),
    CategorySpec(
        "BK",
        "Bakeware",
        5,
        (12, 48),
        ("Loaf Pan", "Sheet Pan Half Size", "Muffin Tin 12-Cup", "Pie Dish 9 in"),
        ("Aluminized Steel", "Stoneware", "Glass"),
    ),
    CategorySpec(
        "TW",
        "Tableware",
        0,
        (9, 64),
        ("Dinner Plate", "Salad Plate", "Pasta Bowl", "Serving Platter"),
        ("Speckled Oat", "Matte Charcoal", "Glazed Sea Salt"),
    ),
    CategorySpec(
        "DW",
        "Drinkware",
        3,
        (8, 42),
        ("Tumbler 12 oz", "Wine Glass Set of 2", "Carafe 1 L", "Highball Glass Set of 4"),
        ("Clear", "Smoke", "Amber"),
    ),
    CategorySpec(
        "KT",
        "Kitchen Tools",
        5,
        (6, 39),
        ("Chef Knife 8 in", "Wooden Spoon Set", "Silicone Spatula", "Bench Scraper", "Whisk 11 in"),
        ("Walnut", "Stainless", "Olive Wood"),
    ),
    CategorySpec(
        "ST",
        "Storage",
        6,
        (10, 58),
        ("Glass Canister 1.5 L", "Pantry Jar Set", "Bread Box", "Spice Jar Set of 6"),
        ("Bamboo Lid", "Steel Lid", "Cork Lid"),
    ),
    CategorySpec(
        "LN",
        "Linens",
        4,
        (14, 72),
        ("Linen Tablecloth", "Tea Towel Set of 3", "Apron", "Napkin Set of 4"),
        ("Natural", "Indigo", "Rust Stripe"),
    ),
    CategorySpec(
        "CT",
        "Coffee & Tea",
        7,
        (18, 165),
        ("Pour-Over Kettle", "French Press 34 oz", "Burr Grinder", "Teapot 1 L"),
        ("Matte Black", "Brushed Steel", "Copper"),
    ),
    CategorySpec(
        "BW",
        "Wood & Boards",
        2,
        (19, 96),
        ("Cutting Board Large", "Serving Board", "Rolling Pin", "Salad Servers"),
        ("Maple", "Walnut", "Acacia"),
    ),
)


@dataclass(frozen=True)
class StaffSpec:
    email: str
    full_name: str
    role: str


STAFF: tuple[StaffSpec, ...] = (
    StaffSpec("owner@kestrel.example", "Jordan Ellis", "OWNER"),
    StaffSpec("manager@kestrel.example", "Priya Raman", "MANAGER"),
    StaffSpec("staff@kestrel.example", "Marcus Lee", "STAFF"),
    StaffSpec("sofia@kestrel.example", "Sofia Alvarez", "STAFF"),
    StaffSpec("analyst@kestrel.example", "Daniel Kim", "ANALYST"),
)
