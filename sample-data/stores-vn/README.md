# Mười cửa hàng mẫu (hư cấu) cho thị trường Việt Nam

*Ten fictional Vietnamese online shops (VND, Asia/Ho_Chi_Minh), each a set of the four import CSV
files. Every shop, product, supplier and customer code is invented.*

Đây là **dữ liệu giả lập**, không phải dữ liệu của cửa hàng thật nào. Tên shop, sản phẩm, nhà cung
cấp và mã khách hàng đều do chương trình sinh ra, mọi sự trùng hợp đều ngoài ý muốn. Bộ dữ liệu dùng
để demo theo từng ngành hàng, và làm mẫu cho khách hàng thấy file xuất từ hệ thống của họ cần có dạng
như thế nào.

| Thư mục | Cửa hàng | Ngành hàng | Sản phẩm | Đơn (30 ngày) |
|---|---|---|---|---|
| `moc-lan-fashion` | Mộc Lan Fashion | Thời trang nữ | 27 | ~460 |
| `hat-ngoc-cosmetics` | Hạt Ngọc Cosmetics | Mỹ phẩm, chăm sóc da | 20 | ~600 |
| `pho-cong-nghe` | Phố Công Nghệ Online | Phụ kiện điện thoại | 18 | ~620 |
| `gom-su-an-nhien` | An Nhiên Home | Gốm sứ, đồ gia dụng | 16 | ~310 |
| `be-yeu-mart` | Bé Yêu Mart | Mẹ và bé | 16 | ~500 |
| `tra-banh-co-ba` | Trà & Bánh Cô Ba | Đặc sản, thực phẩm khô | 16 | ~420 |
| `sach-cay-bang` | Sách Cây Bàng | Sách, văn phòng phẩm | 19 | ~350 |
| `the-thao-chan-troi` | Chân Trời Sport | Dụng cụ thể thao | 14 | ~330 |
| `pet-vui` | Pet Vui Shop | Thú cưng | 14 | ~410 |
| `len-xanh-handmade` | Len Xanh | Đồ len, handmade | 16 | ~220 |

Mỗi thư mục có 4 file theo đúng thứ tự nhập: `products.csv` → `inventory_adjustments.csv` →
`orders.csv` → `order_items.csv`.

## Mỗi cửa hàng có sẵn những tình huống gì

Sau khi nhập đủ 4 file, mỗi cửa hàng có đúng **10 ngoại lệ đang mở**:

| Ngoại lệ | Số lượng | Tình huống |
|---|---|---|
| Oversold | 1 | Hai đơn đang xử lý cần nhiều hàng hơn tồn thực tế |
| Oversell risk | 1 | Hai đơn chờ thanh toán sẽ làm bán vượt |
| Out of stock | 1 | Một mặt hàng đang bán đã hết |
| Below reorder point | 2 | Hai mặt hàng dưới ngưỡng đặt lại, một mặt hàng đã có đơn nhập đang về |
| Fulfillment overdue | 2 | Một đơn trễ khoảng 12 giờ, một đơn trễ hơn 3 ngày (Critical) |
| Stalled after payment | 1 | Đơn đã thanh toán 16 giờ mà chưa xử lý |
| Refund pending | 1 | Đơn đã huỷ 30 giờ nhưng chưa hoàn tiền |
| Order total mismatch | 1 | Tổng tiền đơn lệch 15.000 ₫ so với dòng hàng |

Phần còn lại là lịch sử bình thường: đơn đã giao, đang giao, đang đóng gói, một ít đơn huỷ và hoàn tiền.

## Cách dùng

**Cách 1: tạo cả 10 cửa hàng chỉ bằng một lệnh.** Lệnh này đi qua đúng quy trình onboarding thật:
tạo tổ chức, cửa hàng và tài khoản Owner, rồi nhập 4 file CSV. Dữ liệu được sinh lại theo thời điểm
hiện tại nên luôn "mới".

```bash
SAMPLE_OWNER_PASSWORD='mat-khau-tuy-chon' make load-sample-stores        # môi trường phát triển
SAMPLE_OWNER_PASSWORD='mat-khau-tuy-chon' make stack-load-sample-stores  # trong Docker
make load-sample-stores ARGS="--only pet-vui --replace"                  # một cửa hàng, tạo lại
```

Owner của từng cửa hàng đăng nhập bằng `owner@<thư-mục>.example`, ví dụ
`owner@pet-vui.example`. Nếu không đặt `SAMPLE_OWNER_PASSWORD`, mỗi Owner nhận một mật khẩu tạm in ra
màn hình đúng một lần. Biến này bị từ chối khi `APP_ENV=production`.

**Cách 2: nhập thủ công từng file** trong màn hình **Imports → New import**, theo đúng thứ tự trên.
Cửa hàng phải dùng tiền tệ VND.

**Tạo lại file CSV** (ngày tháng trong file theo ngày sinh dữ liệu):

```bash
make sample-stores-csv
```

## Giới hạn

- Đơn hàng mô phỏng thanh toán trước (chuyển khoản, ví điện tử, thẻ). Mô hình v1 chưa hỗ trợ COD,
  tức đơn đã giao nhưng tiền thu sau khi giao.
- Không có thông tin cá nhân của khách mua hàng; chỉ có mã `KH-xxxxx`.
- Ngày tháng trong file CSV cố định theo lúc sinh. Dùng Cách 1 nếu muốn dữ liệu luôn tính đến hôm nay.
