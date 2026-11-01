"""Ten fictional Vietnamese online shops used as sample templates (VND, Asia/Ho_Chi_Minh).

Every shop, supplier, product and person here is invented for demos; any resemblance to a real
business is unintended. Prices are in thousands of VND and are only plausible orders of magnitude.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierDef:
    name: str
    lead_time_days: int


@dataclass(frozen=True)
class LineDef:
    """A product line: one SKU per variant of each item."""

    code: str
    category: str
    supplier: int  # index into StoreDef.suppliers
    price_k: tuple[int, int]  # price range, thousands of VND
    items: tuple[str, ...]
    variants: tuple[str, ...]


@dataclass(frozen=True)
class StoreDef:
    slug: str
    code: str
    org_name: str
    store_name: str
    vertical: str  # shown in the README, Vietnamese
    owner_name: str
    orders_per_day: int
    suppliers: tuple[SupplierDef, ...]
    lines: tuple[LineDef, ...]


STORES: tuple[StoreDef, ...] = (
    StoreDef(
        slug="moc-lan-fashion",
        code="MLF",
        org_name="Công ty TNHH Mộc Lan",
        store_name="Mộc Lan Fashion",
        vertical="Thời trang nữ",
        owner_name="Trần Thị Mộc Lan",
        orders_per_day=14,
        suppliers=(SupplierDef("Xưởng may Tân Phú", 10), SupplierDef("Vải Sợi Phương Nam", 14)),
        lines=(
            LineDef(
                "VAY",
                "Váy",
                0,
                (259, 549),
                ("Váy midi", "Váy suông", "Váy hoa nhí"),
                ("Đen", "Be", "Xanh"),
            ),
            LineDef(
                "AO",
                "Áo",
                0,
                (159, 359),
                ("Áo sơ mi lụa", "Áo thun basic", "Áo kiểu cổ vuông"),
                ("Trắng", "Hồng", "Đen"),
            ),
            LineDef(
                "QUAN",
                "Quần",
                1,
                (229, 459),
                ("Quần ống rộng", "Quần jean", "Chân váy chữ A"),
                ("Size S", "Size M", "Size L"),
            ),
        ),
    ),
    StoreDef(
        slug="hat-ngoc-cosmetics",
        code="HNC",
        org_name="Hạt Ngọc Beauty",
        store_name="Hạt Ngọc Cosmetics",
        vertical="Mỹ phẩm và chăm sóc da",
        owner_name="Lê Ngọc Hân",
        orders_per_day=18,
        suppliers=(
            SupplierDef("Phân phối Mỹ phẩm Sao Mai", 7),
            SupplierDef("Nhà nhập khẩu Đông Á", 21),
        ),
        lines=(
            LineDef(
                "SRM",
                "Sữa rửa mặt",
                0,
                (129, 289),
                ("Sữa rửa mặt dịu nhẹ", "Gel rửa mặt trà xanh"),
                ("100ml", "200ml"),
            ),
            LineDef(
                "SRM2",
                "Serum",
                1,
                (299, 690),
                ("Serum vitamin C", "Serum B5 phục hồi", "Serum niacinamide"),
                ("15ml", "30ml"),
            ),
            LineDef(
                "KCN",
                "Kem chống nắng",
                1,
                (219, 459),
                ("Kem chống nắng SPF50", "Xịt chống nắng"),
                ("50ml", "100ml"),
            ),
            LineDef(
                "SON",
                "Son môi",
                0,
                (149, 329),
                ("Son kem lì", "Son dưỡng có màu"),
                ("Đỏ gạch", "Hồng đất", "Cam cháy"),
            ),
        ),
    ),
    StoreDef(
        slug="pho-cong-nghe",
        code="PCN",
        org_name="Phố Công Nghệ",
        store_name="Phố Công Nghệ Online",
        vertical="Phụ kiện điện thoại",
        owner_name="Nguyễn Minh Khoa",
        orders_per_day=20,
        suppliers=(SupplierDef("Linh kiện Hưng Phát", 5), SupplierDef("Kho phụ kiện Bình Tây", 9)),
        lines=(
            LineDef(
                "OP",
                "Ốp lưng",
                1,
                (59, 189),
                ("Ốp lưng silicon", "Ốp chống sốc"),
                ("Đen", "Trong suốt", "Xanh navy"),
            ),
            LineDef(
                "CAP", "Cáp sạc", 0, (69, 199), ("Cáp sạc nhanh USB-C", "Cáp bện dù"), ("1m", "2m")
            ),
            LineDef(
                "SAC", "Củ sạc", 0, (149, 459), ("Củ sạc 20W", "Củ sạc 65W GaN"), ("Trắng", "Đen")
            ),
            LineDef(
                "TN",
                "Tai nghe",
                0,
                (199, 890),
                ("Tai nghe không dây", "Tai nghe có dây"),
                ("Trắng", "Đen"),
            ),
        ),
    ),
    StoreDef(
        slug="gom-su-an-nhien",
        code="GSA",
        org_name="Gốm Sứ An Nhiên",
        store_name="An Nhiên Home",
        vertical="Gốm sứ và đồ gia dụng",
        owner_name="Phạm Thu An",
        orders_per_day=9,
        suppliers=(SupplierDef("Lò gốm Hồng Phúc", 18), SupplierDef("Xưởng mây tre Thanh Hà", 12)),
        lines=(
            LineDef(
                "BAT",
                "Bát đĩa",
                0,
                (45, 189),
                ("Bát cơm men lam", "Đĩa tròn men rạn", "Bát canh"),
                ("Trắng ngà", "Xanh lam"),
            ),
            LineDef(
                "COC",
                "Cốc chén",
                0,
                (59, 249),
                ("Cốc sứ quai tròn", "Bộ ấm chén"),
                ("Nâu đất", "Trắng sữa"),
            ),
            LineDef(
                "GIO",
                "Đồ mây tre",
                1,
                (99, 389),
                ("Giỏ mây đựng đồ", "Khay tre", "Lót nồi cói"),
                ("Nhỏ", "Lớn"),
            ),
        ),
    ),
    StoreDef(
        slug="be-yeu-mart",
        code="BYM",
        org_name="Bé Yêu Mart",
        store_name="Bé Yêu Mart",
        vertical="Mẹ và bé",
        owner_name="Đỗ Thị Hồng",
        orders_per_day=16,
        suppliers=(SupplierDef("Phân phối Hạnh Phúc Kids", 6), SupplierDef("Dệt may Bình An", 10)),
        lines=(
            LineDef(
                "TA",
                "Tã bỉm",
                0,
                (189, 429),
                ("Tã quần", "Tã dán"),
                ("Size M", "Size L", "Size XL"),
            ),
            LineDef(
                "BB",
                "Bình sữa",
                0,
                (159, 399),
                ("Bình sữa cổ rộng", "Bình tập uống"),
                ("150ml", "260ml"),
            ),
            LineDef(
                "QA",
                "Quần áo sơ sinh",
                1,
                (89, 259),
                ("Bộ body cotton", "Khăn sữa", "Mũ sơ sinh"),
                ("0-3 tháng", "3-6 tháng"),
            ),
        ),
    ),
    StoreDef(
        slug="tra-banh-co-ba",
        code="TCB",
        org_name="Trà & Bánh Cô Ba",
        store_name="Trà & Bánh Cô Ba",
        vertical="Đặc sản và thực phẩm khô",
        owner_name="Võ Thị Ba",
        orders_per_day=12,
        suppliers=(
            SupplierDef("Hợp tác xã chè Đồi Mây", 8),
            SupplierDef("Cơ sở bánh Hương Quê", 4),
        ),
        lines=(
            LineDef(
                "TRA",
                "Trà",
                0,
                (85, 390),
                ("Trà xanh thượng hạng", "Trà ô long", "Trà sen"),
                ("100g", "250g"),
            ),
            LineDef(
                "BANH",
                "Bánh kẹo",
                1,
                (45, 159),
                ("Bánh pía sầu riêng", "Kẹo dừa", "Bánh đậu xanh"),
                ("Hộp nhỏ", "Hộp lớn"),
            ),
            LineDef(
                "HAT",
                "Hạt dinh dưỡng",
                1,
                (99, 289),
                ("Hạt điều rang muối", "Mix hạt"),
                ("250g", "500g"),
            ),
        ),
    ),
    StoreDef(
        slug="sach-cay-bang",
        code="SCB",
        org_name="Nhà sách Cây Bàng",
        store_name="Sách Cây Bàng",
        vertical="Sách và văn phòng phẩm",
        owner_name="Hoàng Văn Bàng",
        orders_per_day=11,
        suppliers=(
            SupplierDef("Phát hành sách Trường Xuân", 7),
            SupplierDef("Văn phòng phẩm Bút Xanh", 5),
        ),
        lines=(
            LineDef(
                "SACH",
                "Sách",
                0,
                (69, 259),
                ("Tiểu thuyết bìa mềm", "Sách kỹ năng", "Truyện thiếu nhi"),
                ("Tập 1", "Tập 2", "Tập 3"),
            ),
            LineDef("VO", "Vở và sổ", 1, (19, 129), ("Vở kẻ ngang", "Sổ tay bìa da"), ("A5", "B5")),
            LineDef(
                "BUT", "Bút", 1, (9, 99), ("Bút gel", "Bút highlight"), ("Đen", "Xanh", "Bộ 5 màu")
            ),
        ),
    ),
    StoreDef(
        slug="the-thao-chan-troi",
        code="TTC",
        org_name="Thể Thao Chân Trời",
        store_name="Chân Trời Sport",
        vertical="Dụng cụ thể thao",
        owner_name="Bùi Quốc Trung",
        orders_per_day=10,
        suppliers=(SupplierDef("Thể thao Đại Dương", 12), SupplierDef("Xưởng giày Sông Hồng", 20)),
        lines=(
            LineDef(
                "THAM", "Thảm tập", 0, (149, 449), ("Thảm yoga TPE", "Thảm tập gym"), ("6mm", "8mm")
            ),
            LineDef(
                "TA2",
                "Tạ và dây kháng lực",
                0,
                (99, 590),
                ("Tạ tay bọc cao su", "Dây kháng lực"),
                ("2kg", "5kg", "Bộ 5 dây"),
            ),
            LineDef(
                "GIAY",
                "Giày chạy bộ",
                1,
                (459, 1290),
                ("Giày chạy bộ nhẹ", "Giày tập gym"),
                ("Size 40", "Size 42"),
            ),
        ),
    ),
    StoreDef(
        slug="pet-vui",
        code="PTV",
        org_name="Pet Vui",
        store_name="Pet Vui Shop",
        vertical="Thú cưng",
        owner_name="Lý Gia Huy",
        orders_per_day=13,
        suppliers=(
            SupplierDef("Thức ăn thú cưng Miền Đông", 6),
            SupplierDef("Phụ kiện thú cưng Kim Long", 11),
        ),
        lines=(
            LineDef(
                "HAT2", "Thức ăn hạt", 0, (129, 690), ("Hạt cho mèo", "Hạt cho chó"), ("1kg", "3kg")
            ),
            LineDef(
                "PATE", "Pate", 0, (25, 189), ("Pate cá ngừ", "Pate gà"), ("Lon 85g", "Hộp 400g")
            ),
            LineDef(
                "PK",
                "Phụ kiện",
                1,
                (59, 459),
                ("Vòng cổ", "Đệm ngủ", "Cát vệ sinh"),
                ("Nhỏ", "Lớn"),
            ),
        ),
    ),
    StoreDef(
        slug="len-xanh-handmade",
        code="LXH",
        org_name="Len Xanh Handmade",
        store_name="Len Xanh",
        vertical="Đồ len và handmade",
        owner_name="Đặng Thanh Xuân",
        orders_per_day=7,
        suppliers=(SupplierDef("Sợi len Đà Lạt Mây", 15), SupplierDef("Phụ liệu Chợ Lớn", 7)),
        lines=(
            LineDef(
                "LEN",
                "Cuộn len",
                0,
                (35, 129),
                ("Len cotton milk", "Len lông cừu"),
                ("Kem", "Xanh rêu", "Hồng phấn"),
            ),
            LineDef(
                "KIM",
                "Dụng cụ đan móc",
                1,
                (29, 189),
                ("Bộ kim móc", "Kim đan tre"),
                ("Bộ nhỏ", "Bộ đầy đủ"),
            ),
            LineDef(
                "THANH",
                "Thành phẩm",
                0,
                (149, 459),
                ("Khăn len", "Túi len handmade", "Thú bông móc"),
                ("Nhỏ", "Vừa"),
            ),
        ),
    ),
)
